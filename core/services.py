import logging
import time
from decimal import Decimal
from typing import Optional

from django.db import OperationalError, transaction

from .models import Event, Payment, Ticket
from .sparkpesa import (
    SparkPesaError,
    request_stk_payment,
    resolve_sparkpesa_webhook_url,
)
from .utils import (
    attach_qr,
    attach_ticket_pdf,
    build_qr_payload,
    generate_payment_reference,
    send_ticket_email,
)

_logger = logging.getLogger(__name__)

MIN_MPESA_AMOUNT = 10


def get_sparkpesa_callback_url(request=None):
    url = resolve_sparkpesa_webhook_url()
    if url:
        return url
    if request:
        from django.urls import reverse

        return request.build_absolute_uri(reverse("sparkpesa_webhook"))
    return ""


def apply_webhook_refs(payment, event_payload):
    data = event_payload.get("data") or {}
    payment.transaction_ref = (
        event_payload.get("reference")
        or data.get("mpesaReceiptNumber")
        or data.get("transactionReference")
        or payment.transaction_ref
    )
    payment.sparkpesa_transaction_id = (
        event_payload.get("transactionId") or payment.sparkpesa_transaction_id
    )
    return payment


def _mark_email_sent(payment_id: int):
    payment = Payment.objects.get(pk=payment_id)
    payment.payload = {**payment.payload, "email_sent": True}
    payment.save(update_fields=["payload", "updated_at"])


def deliver_ticket_email(ticket_id: int, payment_id: Optional[int] = None) -> bool:
    """Send confirmation email immediately (with one retry)."""
    for attempt in (1, 2):
        try:
            sent = send_ticket_email(ticket_id)
            if sent and payment_id:
                _mark_email_sent(payment_id)
            if sent:
                return True
        except Exception:
            _logger.exception(
                "Ticket email attempt %s failed for ticket_id=%s",
                attempt,
                ticket_id,
            )
        if attempt == 1:
            time.sleep(1)
    return False


def ensure_ticket_email_sent(payment) -> Payment:
    """Resend ticket email when payment is complete but email was never sent."""
    payment.refresh_from_db()
    if payment.status != Payment.Status.COMPLETED:
        return payment
    if payment.payload.get("email_sent"):
        return payment
    if payment.ticket.status != Ticket.Status.PAID:
        return payment
    deliver_ticket_email(payment.ticket_id, payment.pk)
    payment.refresh_from_db()
    return payment


def sync_payment_status(payment):
    """Reconcile pending payments when SparkPesa webhook was missed."""
    payment.refresh_from_db()
    if payment.status != Payment.Status.PENDING:
        return payment

    from .sparkpesa import (
        SparkPesaError,
        lookup_payment_transaction,
        transaction_to_webhook_event,
    )

    try:
        tx = lookup_payment_transaction(
            transaction_id=payment.sparkpesa_transaction_id,
            account_reference=payment.account_reference,
            transaction_ref=payment.transaction_ref,
        )
    except SparkPesaError as exc:
        _logger.warning("SparkPesa sync failed for payment %s: %s", payment.pk, exc)
        return payment

    if not tx:
        return payment

    status = str(tx.get("status") or "").strip().lower()
    if status == "completed":
        return apply_webhook_event(transaction_to_webhook_event(tx))
    if status in {"failed", "cancelled"}:
        data = tx.get("data") if isinstance(tx.get("data"), dict) else {}
        reason = data.get("resultDesc") or tx.get("resultDesc") or "Payment was not completed."
        mark_payment_failed(payment, reason, extra=transaction_to_webhook_event(tx))
        payment.refresh_from_db()
        return payment

    return payment


def initiate_mpesa_payment(ticket, phone, request=None):
    amount = Decimal(ticket.total_price)
    if amount < MIN_MPESA_AMOUNT:
        raise SparkPesaError(f"Minimum M-Pesa amount is KES {MIN_MPESA_AMOUNT}.")

    account_reference = generate_payment_reference("TUK", max_length=12)
    payment = Payment.objects.create(
        ticket=ticket,
        method=Payment.Method.MPESA,
        amount=amount,
        status=Payment.Status.PENDING,
        phone_number=phone,
        account_reference=account_reference,
        transaction_ref="",
        payload={"mpesa_phone": phone},
    )

    try:
        result = request_stk_payment(
            phone_number=phone,
            amount=amount,
            account_reference=account_reference,
            transaction_desc=f"Ticket: {ticket.event.title}"[:100],
            metadata={
                "ticket_id": str(ticket.ticket_id),
                "payment_id": payment.id,
                "account_reference": account_reference,
            },
        )
    except SparkPesaError as exc:
        payment.status = Payment.Status.FAILED
        payment.payload = {
            **payment.payload,
            "error": str(exc),
            "details": exc.details,
        }
        payment.save(update_fields=["status", "payload", "updated_at"])
        ticket.status = Ticket.Status.CANCELLED
        ticket.save(update_fields=["status", "updated_at"])
        raise

    payment.transaction_ref = result.get("reference") or ""
    payment.sparkpesa_transaction_id = result.get("transactionId") or ""
    payment.payload = {
        **payment.payload,
        "sparkpesa_init": result,
        "callback_url": resolve_sparkpesa_webhook_url(),
    }
    payment.save(
        update_fields=[
            "transaction_ref",
            "sparkpesa_transaction_id",
            "payload",
            "updated_at",
        ]
    )
    return payment


def fulfill_ticket_payment(payment, extra_payload=None):
    payment = Payment.objects.select_related("ticket", "ticket__event", "ticket__ticket_type").get(
        pk=payment.pk
    )

    if payment.status == Payment.Status.COMPLETED:
        if extra_payload:
            apply_webhook_refs(payment, extra_payload)
            payment.payload = {**payment.payload, "webhook": extra_payload}
            payment.save(update_fields=["transaction_ref", "sparkpesa_transaction_id", "payload", "updated_at"])
        if not payment.payload.get("email_sent") and payment.ticket.status == Ticket.Status.PAID:
            deliver_ticket_email(payment.ticket_id, payment.pk)
        return payment

    ticket_id = None
    try:
        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .select_related("ticket", "ticket__event", "ticket__ticket_type")
                .get(pk=payment.pk)
            )

            if extra_payload:
                apply_webhook_refs(payment, extra_payload)
                payment.payload = {**payment.payload, "webhook": extra_payload}

            already_completed = payment.status == Payment.Status.COMPLETED

            ticket = payment.ticket
            event = ticket.event

            if ticket.status != Ticket.Status.PAID:
                ticket.status = Ticket.Status.PAID
                ticket.qr_token = build_qr_payload(ticket)
                attach_qr(ticket)
                attach_ticket_pdf(ticket)
                ticket.save()

                event.slots_left = max(0, event.slots_left - ticket.quantity)
                if event.slots_left == 0:
                    event.status = Event.Status.SOLD_OUT
                event.save(update_fields=["slots_left", "status", "updated_at"])

            if not already_completed:
                payment.status = Payment.Status.COMPLETED
                payment.payload = {**payment.payload, "email_sent": False}
                payment.save(
                    update_fields=[
                        "status",
                        "transaction_ref",
                        "sparkpesa_transaction_id",
                        "payload",
                        "updated_at",
                    ]
                )
            ticket_id = ticket.pk
    except OperationalError:
        _logger.warning("Database busy fulfilling payment %s", payment.pk)
        payment.refresh_from_db()
        return payment

    payment.refresh_from_db()
    if ticket_id and payment.ticket.status == Ticket.Status.PAID:
        if not payment.payload.get("email_sent"):
            deliver_ticket_email(ticket_id, payment.pk)
            payment.refresh_from_db()

    return payment


def apply_webhook_event(event_payload: dict):
    from .models import Payment

    data = event_payload.get("data") if isinstance(event_payload.get("data"), dict) else {}
    account_ref = str(
        data.get("accountReference") or event_payload.get("accountReference") or ""
    ).strip()
    stk_ref = str(event_payload.get("reference") or "").strip()
    tx_id = str(event_payload.get("transactionId") or "").strip()

    payment = None
    if account_ref:
        payment = Payment.objects.filter(account_reference=account_ref).select_related("ticket").first()
    if payment is None and stk_ref:
        payment = (
            Payment.objects.filter(transaction_ref=stk_ref)
            .select_related("ticket")
            .first()
        )
    if payment is None and tx_id:
        payment = (
            Payment.objects.filter(sparkpesa_transaction_id=tx_id)
            .select_related("ticket")
            .first()
        )

    if payment is None:
        return None

    event = str(event_payload.get("event") or "").strip().lower()
    status = str(event_payload.get("status") or "").strip().lower()

    completed = event == "payment.completed" or status == "completed"
    failed = event == "payment.failed" or status in {"failed", "cancelled"}

    try:
        if completed:
            return fulfill_ticket_payment(payment, extra_payload=event_payload)
        if failed:
            reason = data.get("resultDesc") or event_payload.get("message") or "Payment was not completed."
            mark_payment_failed(payment, reason, extra=event_payload)
            return payment
    except OperationalError:
        _logger.warning("Database busy processing webhook for payment %s", payment.pk)
        return payment

    _logger.info(
        "SparkPesa webhook ignored for payment %s event=%s status=%s",
        payment.pk,
        event or "(none)",
        status or "(none)",
    )
    return payment


def mark_payment_failed(payment, message, extra=None):
    if extra:
        apply_webhook_refs(payment, extra)
    payment.status = Payment.Status.FAILED
    payment.payload = {**payment.payload, "error": message, **({"webhook": extra} if extra else {})}
    payment.save(
        update_fields=[
            "status",
            "transaction_ref",
            "sparkpesa_transaction_id",
            "payload",
            "updated_at",
        ]
    )
    if payment.ticket.status == Ticket.Status.PENDING:
        payment.ticket.status = Ticket.Status.CANCELLED
        payment.ticket.save(update_fields=["status", "updated_at"])
