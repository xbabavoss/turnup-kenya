import base64
import io
import json
import logging
from uuid import uuid4

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

_logger = logging.getLogger(__name__)

PDF_W, PDF_H = letter


def generate_payment_reference(prefix="TXN", max_length=12):
    """Generate a reference; default max 12 chars for M-Pesa accountReference."""
    prefix = (prefix or "TXN")[:max_length]
    room = max_length - len(prefix)
    if room <= 0:
        return prefix[:max_length]
    return f"{prefix}{uuid4().hex[:room].upper()}"


def build_qr_payload(ticket):
    payload = {
        "ticket_id": str(ticket.ticket_id),
        "attendee_name": ticket.attendee_name,
        "event_id": ticket.event_id,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return encoded


def _qr_image_bytes(ticket):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(ticket.qr_token)
    qr.make(fit=True)
    image = qr.make_image(fill_color="white", back_color="black")
    stream = io.BytesIO()
    image.save(stream, "PNG")
    stream.seek(0)
    return stream


def attach_qr(ticket):
    stream = _qr_image_bytes(ticket)
    ticket.qr_image.save(f"ticket-{ticket.ticket_id}.png", ContentFile(stream.getvalue()), save=False)


def render_ticket_pdf_bytes(ticket) -> bytes:
    """Build ticket PDF in memory (reliable for email; no media file required)."""
    if not ticket.qr_token:
        ticket.qr_token = build_qr_payload(ticket)

    qr_stream = _qr_image_bytes(ticket)
    pdf_stream = io.BytesIO()
    c = canvas.Canvas(pdf_stream, pagesize=letter)

    margin = 36
    content_w = PDF_W - margin * 2
    y = PDF_H - margin

    c.setFillColor(colors.HexColor("#12151c"))
    c.rect(0, 0, PDF_W, PDF_H, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "TURN UP KENYA")
    y -= 28

    c.setFont("Helvetica-Bold", 20)
    title = (ticket.event.title or "Event")[:55]
    c.drawString(margin, y, title.upper())
    y -= 22

    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor("#b8bcc6"))
    when = (
        ticket.event.starts_at.strftime("%a %d %B %Y, %I:%M %p")
        if ticket.event.starts_at
        else ""
    )
    c.drawString(margin, y, when)
    y -= 16
    venue_line = ticket.event.venue
    if ticket.event.location:
        venue_line = f"{venue_line}, {ticket.event.location}"
    c.drawString(margin, y, venue_line[:70])
    y -= 28

    qr_size = 108
    c.drawImage(
        ImageReader(qr_stream),
        PDF_W - margin - qr_size,
        PDF_H - margin - qr_size - 10,
        width=qr_size,
        height=qr_size,
        preserveAspectRatio=True,
        mask="auto",
    )

    bar_h = 32
    c.setFillColor(colors.HexColor("#f0c419"))
    c.rect(margin, y - bar_h, content_w, bar_h, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 13)
    type_name = ticket.ticket_type.name if ticket.ticket_type_id else "General Admission"
    c.drawCentredString(PDF_W / 2, y - bar_h + 10, type_name)
    y -= bar_h

    row_h = 44
    c.setFillColor(colors.black)
    c.rect(margin, y - row_h, content_w, row_h, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin + 12, y - row_h + 14, ticket.attendee_name[:40])
    c.drawRightString(PDF_W - margin - 12, y - row_h + 14, f"KES {int(ticket.total_price)}")
    y -= row_h + 24

    c.setFillColor(colors.HexColor("#9ca3af"))
    c.setFont("Helvetica", 10)
    lines = [
        f"Ticket ID: {ticket.ticket_id}",
        f"Quantity: {ticket.quantity}",
        "Present this PDF at entry. Staff will scan the QR code above.",
    ]
    for line in lines:
        c.drawString(margin, y, line)
        y -= 14

    c.showPage()
    c.save()
    return pdf_stream.getvalue()


def attach_ticket_pdf(ticket):
    """Save ticket PDF to storage (portal/download)."""
    data = render_ticket_pdf_bytes(ticket)
    ticket.pdf_ticket.save(
        f"ticket-{ticket.ticket_id}.pdf",
        ContentFile(data),
        save=False,
    )


from .url_helpers import _force_https


def _absolute_media_url(path):
    if not path:
        return ""
    if path.startswith("http"):
        return _force_https(path)
    rel = path if path.startswith("/") else f"/{path}"
    base = getattr(settings, "SITE_URL", "").rstrip("/")
    if base:
        return f"{_force_https(base)}{rel}"
    return rel


def _ticket_pdf_bytes(ticket) -> bytes:
    """PDF bytes for attachment; reads saved file or builds in memory."""
    if ticket.pdf_ticket:
        try:
            with ticket.pdf_ticket.open("rb") as pdf_file:
                return pdf_file.read()
        except OSError:
            _logger.warning(
                "Could not read PDF for ticket %s; regenerating in memory",
                ticket.ticket_id,
            )
    return render_ticket_pdf_bytes(ticket)


def send_ticket_email(ticket_id):
    from .models import SiteSettings, Ticket

    if not getattr(settings, "EMAIL_HOST_USER", ""):
        _logger.error(
            "EMAIL_HOST_USER is not set; cannot send ticket email for ticket pk=%s",
            ticket_id,
        )
        return False

    ticket = Ticket.objects.select_related("event", "ticket_type").get(pk=ticket_id)
    if not ticket.attendee_email:
        _logger.warning("No email on ticket %s", ticket.ticket_id)
        return False

    update_fields = []
    if not ticket.qr_token:
        ticket.qr_token = build_qr_payload(ticket)
        update_fields.append("qr_token")
    if not ticket.qr_image:
        attach_qr(ticket)
        update_fields.append("qr_image")
    if not ticket.pdf_ticket:
        attach_ticket_pdf(ticket)
        update_fields.append("pdf_ticket")
    if update_fields:
        ticket.save(update_fields=update_fields)

    pdf_bytes = _ticket_pdf_bytes(ticket)
    site = SiteSettings.load()
    poster_url = ""
    if ticket.event.poster:
        try:
            poster_url = _absolute_media_url(ticket.event.poster.url)
        except (ValueError, OSError):
            poster_url = ""

    context = {"ticket": ticket, "site": site, "poster_url": poster_url}
    html_body = render_to_string("emails/ticket_confirmation.html", context)
    text_body = (
        f"Thank you for your purchase.\n\n"
        f"{ticket.event.title}\n"
        f"{ticket.event.starts_at}\n"
        f"{ticket.event.venue}\n\n"
        f"{ticket.ticket_type.name}: {ticket.attendee_name}\n"
        f"KES {int(ticket.total_price)}\n\n"
        f"Your ticket is attached as a PDF. Show it at the venue.\n"
        f"Ticket ID: {ticket.ticket_id}\n"
    )
    email = EmailMultiAlternatives(
        subject=f"Your ticket for {ticket.event.title}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[ticket.attendee_email.strip()],
    )
    email.attach_alternative(html_body, "text/html")
    email.attach(
        f"TurnUpKenya-Ticket-{ticket.ticket_id}.pdf",
        pdf_bytes,
        "application/pdf",
    )

    try:
        email.send(fail_silently=False)
        _logger.info("Ticket email sent to %s for %s", ticket.attendee_email, ticket.ticket_id)
        return True
    except Exception:
        _logger.exception(
            "Failed to send ticket email to %s (host=%s user=%s)",
            ticket.attendee_email,
            getattr(settings, "EMAIL_HOST", ""),
            getattr(settings, "EMAIL_HOST_USER", ""),
        )
        return False
