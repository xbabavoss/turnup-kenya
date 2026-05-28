from django import template
from django.db.models import Min

register = template.Library()


@register.filter
def event_image(event):
    if getattr(event, "poster", None):
        try:
            return event.poster.url
        except (ValueError, AttributeError):
            pass
    return ""


@register.simple_tag
def event_min_price(event):
    if getattr(event, "ticket_price", None):
        return int(event.ticket_price)
    prices = event.ticket_types.aggregate(m=Min("price"))["m"]
    return int(prices) if prices else 0


@register.filter
def is_sold_out(event):
    status = getattr(event, "status", "")
    slots = getattr(event, "slots_left", getattr(event, "seats_left", 1))
    return status == "sold_out" or slots <= 0


@register.filter
def event_slots(event):
    return getattr(event, "slots_left", getattr(event, "seats_left", 0))


@register.filter
def split_lineup(value):
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]
