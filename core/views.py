import json
import logging
from decimal import Decimal

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .customers import get_or_create_customer, normalize_phone
from .forms import QuickPurchaseForm
from .models import Event, Payment, SiteSettings, Ticket
from .services import (
    MIN_MPESA_AMOUNT,
    apply_webhook_event,
    initiate_mpesa_payment,
    sync_payment_status,
)
from .sparkpesa import SparkPesaError

_logger = logging.getLogger(__name__)


def health(request):
    from django.http import JsonResponse

    return JsonResponse({"status": "ok"})


def sparkpesa_health(request):
    from django.http import JsonResponse

    from .sparkpesa import sparkpesa_config_status

    return JsonResponse(sparkpesa_config_status())


def _upcoming_events():
    return Event.objects.filter(starts_at__gte=timezone.now()).prefetch_related("ticket_types")


def home(request):
    qs = _upcoming_events()
    featured = list(qs.filter(featured=True).order_by("starts_at")[:3])
    if len(featured) < 3:
        seen = {e.pk for e in featured}
        for event in qs.order_by("starts_at"):
            if event.pk not in seen:
                featured.append(event)
                seen.add(event.pk)
            if len(featured) >= 3:
                break

    site = SiteSettings.load()
    hero_image = ""
    if site.hero_image:
        hero_image = site.hero_image.url
    else:
        for event in featured:
            if event.poster:
                hero_image = event.poster.url
                break

    now = timezone.now()
    week_end = now + timezone.timedelta(days=7)
    events_this_week = qs.filter(starts_at__lte=week_end).count()

    return render(
        request,
        "core/home.html",
        {
            "hero_image": hero_image,
            "featured_events": featured,
            "events_this_week": events_this_week,
        },
    )


def event_list(request):
    events = Event.objects.prefetch_related("ticket_types").order_by("starts_at")
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("category", "All")

    categories = ["All"] + sorted({c for c in Event.objects.values_list("category", flat=True) if c})
    if q:
        events = events.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(venue__icontains=q)
            | Q(location__icontains=q)
        )
    if cat and cat != "All":
        events = events.filter(category__iexact=cat)

    return render(
        request,
        "core/event_list.html",
        {
            "events": events,
            "categories": categories,
            "active_category": cat or "All",
            "search_q": q,
            "event_count": events.count(),
        },
    )


def event_detail(request, slug):
    event = get_object_or_404(Event.objects.prefetch_related("ticket_types"), slug=slug)
    return render(request, "core/event_detail.html", {"event": event})


def ticket_success(request, ticket_id):
    ticket = get_object_or_404(Ticket.objects.select_related("customer", "event"), ticket_id=ticket_id)
    return render(request, "core/ticket_success.html", {"ticket": ticket})


def about_page(request):
    return render(request, "core/about.html")


def _wants_json(request):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept


def _json_error(message, status=400, details=None):
    payload = {"ok": False, "error": message}
    if details:
        payload["details"] = details
        if isinstance(details, list):
            parts = [
                f"{d.get('field', '')}: {d.get('message', '')}".strip(": ")
                for d in details
                if isinstance(d, dict)
            ]
            if parts:
                payload["error"] = f"{message} ({'; '.join(parts)})"
    return JsonResponse(payload, status=status)


@require_POST
def quick_purchase(request, slug):
    wants_json = _wants_json(request)

    event = Event.objects.filter(slug=slug).prefetch_related("ticket_types").first()
    if not event:
        msg = "This event is not available for purchase yet."
        if wants_json:
            return _json_error(msg, 404)
        messages.error(request, msg)
        return redirect("event_list")

    ticket_type = event.ticket_types.first()
    if not ticket_type:
        msg = "No ticket types configured for this event."
        if wants_json:
            return _json_error(msg, 400)
        messages.error(request, msg)
        return redirect("event_detail", slug=slug)

    if event.slots_left <= 0 or event.status == Event.Status.SOLD_OUT:
        msg = "This event is sold out."
        if wants_json:
            return _json_error(msg, 400)
        messages.error(request, msg)
        return redirect("event_detail", slug=slug)

    form = QuickPurchaseForm(request.POST)
    if not form.is_valid():
        msg = "Please enter a valid email and phone number."
        if wants_json:
            return _json_error(msg, 400, form.errors)
        messages.error(request, msg)
        return redirect("event_detail", slug=slug)

    quantity = form.cleaned_data["quantity"]
    email = form.cleaned_data["email"]
    phone = normalize_phone(form.cleaned_data["mpesa_phone"])
    full_name = form.cleaned_data.get("full_name") or email.split("@")[0]

    customer = get_or_create_customer(phone, email, full_name)
    total = Decimal(ticket_type.price) * quantity

    if total < MIN_MPESA_AMOUNT:
        msg = f"Minimum payment is KES {MIN_MPESA_AMOUNT}. This ticket total is KES {total}."
        if wants_json:
            return _json_error(msg, 400)
        messages.error(request, msg)
        return redirect("event_detail", slug=slug)

    ticket = Ticket.objects.create(
        customer=customer,
        event=event,
        ticket_type=ticket_type,
        attendee_name=full_name,
        attendee_email=email,
        attendee_phone=phone,
        quantity=quantity,
        unit_price=ticket_type.price,
        total_price=total,
        status=Ticket.Status.PENDING,
    )

    try:
        payment = initiate_mpesa_payment(ticket, phone, request=request)
    except SparkPesaError as exc:
        if wants_json:
            status = 400 if exc.status_code and exc.status_code < 500 else 502
            return _json_error(str(exc), status, exc.details)
        messages.error(request, str(exc))
        return redirect("event_detail", slug=slug)

    if wants_json:
        return JsonResponse(
            {
                "ok": True,
                "payment_id": payment.id,
                "account_reference": payment.account_reference,
                "transaction_ref": payment.transaction_ref,
                "message": "STK push sent. Check your phone and enter your M-Pesa PIN.",
                "status_url": reverse("payment_status", kwargs={"payment_id": payment.id}),
            }
        )

    messages.info(request, "Check your phone for the M-Pesa prompt.")
    return redirect("event_detail", slug=slug)


@require_GET
def payment_status(request, payment_id):
    """Read payment state; syncs with SparkPesa if webhook was missed."""
    payment = get_object_or_404(Payment.objects.select_related("ticket"), pk=payment_id)
    if payment.status == Payment.Status.PENDING:
        payment = sync_payment_status(payment)
    data = {
        "ok": True,
        "payment_id": payment.id,
        "account_reference": payment.account_reference,
        "transaction_ref": payment.transaction_ref,
        "status": payment.status,
        "ticket_id": str(payment.ticket.ticket_id),
        "email": payment.ticket.attendee_email,
    }
    if payment.status == Payment.Status.FAILED:
        data["ok"] = False
        data["error"] = payment.payload.get("error") or "Payment failed. Please try again."
    elif payment.status == Payment.Status.COMPLETED:
        data["message"] = "Payment successful. Your ticket has been sent to your email."
    else:
        data["message"] = "Waiting for M-Pesa confirmation…"
    return JsonResponse(data)


@csrf_exempt
def sparkpesa_webhook(request):
    if request.method == "GET":
        return JsonResponse({"status": "ok", "service": "Turn Up Kenya webhooks"})

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    raw = request.body.decode("utf-8", errors="replace")
    _logger.info(
        "SparkPesa webhook POST len=%s content_type=%s",
        len(raw),
        request.content_type,
    )
    try:
        event = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        _logger.warning("SparkPesa webhook invalid JSON: %s", raw[:500])
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    _logger.info(
        "SparkPesa webhook event=%s status=%s tx=%s ref=%s",
        event.get("event"),
        event.get("status"),
        event.get("transactionId"),
        event.get("reference"),
    )
    apply_webhook_event(event)
    return JsonResponse({"received": True})
