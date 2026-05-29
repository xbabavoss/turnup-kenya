"""Ticket email via Resend HTTP API (Railway-friendly) or SMTP fallback."""

from __future__ import annotations

import base64
import logging

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

_logger = logging.getLogger(__name__)


def email_provider_configured() -> bool:
    if getattr(settings, "RESEND_API_KEY", ""):
        return True
    return bool(getattr(settings, "EMAIL_HOST_USER", "") and getattr(settings, "EMAIL_HOST", ""))


def send_ticket_message(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    pdf_filename: str,
    pdf_bytes: bytes,
) -> bool:
    if getattr(settings, "RESEND_API_KEY", ""):
        return _send_via_resend(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            pdf_filename=pdf_filename,
            pdf_bytes=pdf_bytes,
        )
    return _send_via_smtp(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        pdf_filename=pdf_filename,
        pdf_bytes=pdf_bytes,
    )


def _send_via_resend(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    pdf_filename: str,
    pdf_bytes: bytes,
) -> bool:
    from_email = (
        getattr(settings, "RESEND_FROM_EMAIL", "")
        or getattr(settings, "DEFAULT_FROM_EMAIL", "")
    )
    if not from_email:
        _logger.error("RESEND_FROM_EMAIL or DEFAULT_FROM_EMAIL is required for Resend")
        return False

    payload = {
        "from": from_email,
        "to": [to_email.strip()],
        "subject": subject,
        "html": html_body,
        "text": text_body,
        "attachments": [
            {
                "filename": pdf_filename,
                "content": base64.b64encode(pdf_bytes).decode("ascii"),
            }
        ],
    }
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
    except requests.RequestException:
        _logger.exception("Resend API request failed for %s", to_email)
        return False

    if response.status_code >= 400:
        _logger.error(
            "Resend API error %s for %s: %s",
            response.status_code,
            to_email,
            response.text[:500],
        )
        return False

    _logger.info("Ticket email sent via Resend to %s", to_email)
    return True


def _send_via_smtp(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    pdf_filename: str,
    pdf_bytes: bytes,
) -> bool:
    if not getattr(settings, "EMAIL_HOST_USER", ""):
        _logger.error("EMAIL_HOST_USER is not set; cannot send via SMTP")
        return False

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email.strip()],
    )
    email.attach_alternative(html_body, "text/html")
    email.attach(pdf_filename, pdf_bytes, "application/pdf")

    try:
        email.send(fail_silently=False)
        _logger.info("Ticket email sent via SMTP to %s", to_email)
        return True
    except Exception:
        _logger.exception(
            "SMTP failed for %s (host=%s) — use RESEND_API_KEY on Railway",
            to_email,
            getattr(settings, "EMAIL_HOST", ""),
        )
        return False
