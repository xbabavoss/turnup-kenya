import re
from .models import Customer


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("254"):
        return digits
    if digits.startswith("0"):
        return "254" + digits[1:]
    if len(digits) == 9:
        return "254" + digits
    return digits


def get_or_create_customer(phone: str, email: str, full_name: str = "") -> Customer:
    normalized = normalize_phone(phone)
    customer, created = Customer.objects.get_or_create(
        phone=normalized,
        defaults={"email": email.strip().lower(), "full_name": full_name.strip()},
    )
    if not created:
        updated = []
        if email and customer.email != email.lower():
            customer.email = email.strip().lower()
            updated.append("email")
        if full_name and not customer.full_name:
            customer.full_name = full_name.strip()
            updated.append("full_name")
        if updated:
            customer.save(update_fields=updated)
    return customer
