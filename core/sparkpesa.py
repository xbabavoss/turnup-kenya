"""SparkPesa M-Pesa STK Push (request-payment) and wallet polling."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from decimal import Decimal
from typing import Any
import requests
from django.conf import settings

_logger = logging.getLogger(__name__)


class SparkPesaError(Exception):
    """Configuration or API error."""

    def __init__(self, message, details=None, status_code=None):
        super().__init__(message)
        self.details = details or []
        self.status_code = status_code


def _strip_env(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'")


def _base_url() -> str:
    return (
        _strip_env(getattr(settings, "SPARKPESA_BASE_URL", ""))
        or "https://www.sparkpesa.io/api/v1"
    ).rstrip("/")


def _api_key() -> str:
    key = _strip_env(getattr(settings, "SPARKPESA_API_KEY", ""))
    if not key:
        raise SparkPesaError("Missing SPARKPESA_API_KEY")
    return key


def _api_secret() -> str:
    secret = _strip_env(getattr(settings, "SPARKPESA_API_SECRET", ""))
    if not secret:
        raise SparkPesaError("Missing SPARKPESA_API_SECRET")
    return secret


def _wallet_code() -> str:
    return _strip_env(getattr(settings, "SPARKPESA_WALLET_CODE", ""))


def _wallet_id() -> str:
    return _strip_env(getattr(settings, "SPARKPESA_WALLET_ID", ""))


def resolve_sparkpesa_webhook_url() -> str:
    """Public webhook URL (trailing slash for Django APPEND_SLASH)."""
    explicit = _strip_env(getattr(settings, "SPARKPESA_WEBHOOK_URL", ""))
    if not explicit:
        explicit = _strip_env(getattr(settings, "SPARKPESA_CALLBACK_URL", ""))
    if explicit:
        return explicit.rstrip("/") + "/"
    base = _strip_env(getattr(settings, "SITE_URL", "")).rstrip("/")
    if base:
        return f"{base}/webhooks/sparkpesa/"
    return ""


def _amount_for_signature(amount: Any) -> str:
    if amount is None or amount == "":
        return ""
    if isinstance(amount, bool):
        return str(amount)
    if isinstance(amount, int):
        return str(amount)
    if isinstance(amount, float) and amount.is_integer():
        return str(int(amount))
    if isinstance(amount, Decimal) and amount == amount.to_integral_value():
        return str(int(amount))
    return str(amount)


def _payment_signature_string(
    *,
    timestamp: int,
    wallet_code: str = "",
    currency: str = "",
    phone_number: str = "",
    amount: str = "",
    account_reference: str = "",
) -> str:
    return (
        f"{_api_key()}{timestamp}"
        f"{wallet_code}{currency}{phone_number}{amount}{account_reference}"
    )


def _sign_payment_payload(payload: dict[str, Any]) -> tuple[str, int]:
    timestamp = int(time.time())
    wallet_code = str(payload.get("walletCode") or "")
    currency = str(payload.get("currency") or "")
    phone = str(payload.get("phoneNumber") or "")
    amount = _amount_for_signature(payload.get("amount", ""))
    account_ref = str(payload.get("accountReference") or "")
    sig_string = _payment_signature_string(
        timestamp=timestamp,
        wallet_code=wallet_code,
        currency=currency,
        phone_number=phone,
        amount=amount,
        account_reference=account_ref,
    )
    signature = hmac.new(
        _api_secret().encode("utf-8"),
        sig_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return signature, timestamp


def _format_sparkpesa_details(details: Any) -> str:
    if isinstance(details, str):
        return details.strip()
    if isinstance(details, list):
        parts: list[str] = []
        for item in details:
            if isinstance(item, str):
                parts.append(item.strip())
            elif isinstance(item, dict):
                field = str(item.get("field") or "").strip()
                msg = str(item.get("message") or item.get("msg") or "").strip()
                if field and msg:
                    parts.append(f"{field}: {msg}")
                elif msg:
                    parts.append(msg)
        return "; ".join(parts) if parts else str(details)
    return str(details)


def _wallet_payload() -> dict[str, str]:
    wallet_id = _wallet_id()
    wallet_code = _wallet_code()
    if wallet_id:
        return {"walletId": wallet_id}
    if wallet_code:
        return {"walletCode": wallet_code}
    raise SparkPesaError("Missing SPARKPESA_WALLET_CODE or SPARKPESA_WALLET_ID")


def _post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    signature, timestamp = _sign_payment_payload(payload)
    url = f"{_base_url()}{endpoint}"
    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key()}",
            "X-Signature": signature,
            "X-Timestamp": str(timestamp),
        },
        json=payload,
        timeout=45,
    )
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text[:500]}
    if not response.ok:
        err = body.get("error") or body.get("message") or response.text or f"HTTP {response.status_code}"
        details = body.get("details")
        if details:
            err = f"{err}: {_format_sparkpesa_details(details)}"
        raise SparkPesaError(err, details=details, status_code=response.status_code)
    if not isinstance(body, dict):
        raise SparkPesaError(f"SparkPesa returned unexpected body: {body}")
    return body


def request_stk_payment(
    *,
    phone_number: str,
    amount,
    account_reference: str,
    transaction_desc: str = "",
    callback_url: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    account_reference = (account_reference or "").strip()
    if not account_reference:
        raise SparkPesaError("accountReference is required for M-Pesa payment.")

    amount_int = int(Decimal(amount).to_integral_value())
    if amount_int < 10:
        raise SparkPesaError("Amount must be at least KES 10 for M-Pesa STK push.")

    phone_number = (phone_number or "").strip()
    if not phone_number.startswith("254") or len(phone_number) != 12:
        raise SparkPesaError("Phone number must be in format 254XXXXXXXXX.")

    payload: dict[str, Any] = {
        **_wallet_payload(),
        "phoneNumber": phone_number,
        "amount": amount_int,
        "currency": "KES",
        "accountReference": account_reference,
        "transactionDesc": transaction_desc or f"Ticket {account_reference}"[:100],
    }
    webhook_url = callback_url or resolve_sparkpesa_webhook_url()
    if webhook_url:
        payload["callbackUrl"] = webhook_url
    if metadata:
        payload["metadata"] = metadata

    body = _post("/payments/request-payment", payload)
    _logger.info(
        "SparkPesa STK account_ref=%s tx=%s amount=%s",
        account_reference,
        body.get("transactionId"),
        amount_int,
    )
    return body
