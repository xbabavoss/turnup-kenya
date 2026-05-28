import json
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from .forms import PortalEventForm, SiteSettingsForm
from .models import Customer, Event, Payment, SiteSettings, Ticket


def _save_event_from_form(form, user):
    event = form.save(commit=False)
    if not event.organizer_id:
        event.organizer = user
    if not event.slug:
        base = slugify(event.title) or "event"
        slug = base
        n = 1
        qs = Event.objects.filter(slug=slug)
        if event.pk:
            qs = qs.exclude(pk=event.pk)
        while qs.exists():
            slug = f"{base}-{n}"
            n += 1
            qs = Event.objects.filter(slug=slug)
            if event.pk:
                qs = qs.exclude(pk=event.pk)
        event.slug = slug
    if event.slots_left == 0 and event.available_seats:
        event.slots_left = event.available_seats
    event.save()
    event.ensure_default_ticket()
    return event


@login_required
@user_passes_test(lambda u: u.is_staff)
def portal_dashboard(request):
    revenue = Ticket.objects.filter(status=Ticket.Status.PAID).aggregate(t=Sum("total_price"))["t"] or Decimal("0")
    return render(
        request,
        "portal/dashboard.html",
        {
            "events_count": Event.objects.count(),
            "tickets_count": Ticket.objects.filter(status=Ticket.Status.PAID).count(),
            "customers_count": Customer.objects.count(),
            "revenue": revenue,
            "recent_tickets": Ticket.objects.filter(status=Ticket.Status.PAID)
            .select_related("customer", "event")
            .order_by("-created_at")[:12],
            "sales_by_event": (
                Ticket.objects.filter(status=Ticket.Status.PAID)
                .values("event__title", "event__slug")
                .annotate(count=Count("id"), revenue=Sum("total_price"))
                .order_by("-revenue")[:8]
            ),
        },
    )


@login_required
@user_passes_test(lambda u: u.is_staff)
def portal_events(request):
    events = Event.objects.order_by("-starts_at")
    event_form = PortalEventForm()
    edit_data = None
    edit_id = request.GET.get("edit")
    if edit_id:
        edit_event = get_object_or_404(Event, pk=edit_id)
        edit_data = {
            "id": edit_event.pk,
            "title": edit_event.title,
            "description": edit_event.description,
            "venue": edit_event.venue,
            "location": edit_event.location,
            "category": edit_event.category,
            "starts": edit_event.starts_at.strftime("%Y-%m-%dT%H:%M"),
            "ends": edit_event.ends_at.strftime("%Y-%m-%dT%H:%M"),
            "price": str(edit_event.ticket_price),
            "seats": edit_event.available_seats,
            "slots": edit_event.slots_left,
            "status": edit_event.status,
            "lineup": edit_event.lineup,
            "featured": edit_event.featured,
            "poster": edit_event.poster.url if edit_event.poster else "",
        }
    return render(
        request,
        "portal/events_list.html",
        {
            "events": events,
            "event_form": event_form,
            "edit_data_json": json.dumps(edit_data) if edit_data else "null",
        },
    )


@login_required
@user_passes_test(lambda u: u.is_staff)
@require_http_methods(["POST"])
def portal_event_save(request):
    pk = request.POST.get("event_id")
    instance = get_object_or_404(Event, pk=pk) if pk else None
    form = PortalEventForm(request.POST, request.FILES, instance=instance)
    if form.is_valid():
        _save_event_from_form(form, request.user)
        messages.success(request, "Event saved.")
    else:
        messages.error(request, "Could not save event. Check the form.")
    return redirect("portal_events")


@login_required
@user_passes_test(lambda u: u.is_staff)
@require_http_methods(["POST"])
def portal_event_delete(request, pk):
    get_object_or_404(Event, pk=pk).delete()
    messages.success(request, "Event deleted.")
    return redirect("portal_events")


@login_required
@user_passes_test(lambda u: u.is_staff)
def portal_payments(request):
    payments = Payment.objects.select_related(
        "ticket", "ticket__event", "ticket__customer"
    ).order_by("-created_at")
    status = request.GET.get("status")
    if status:
        payments = payments.filter(status=status)
    return render(
        request,
        "portal/payments.html",
        {
            "payments": payments,
            "active_status": status,
            "status_choices": Payment.Status.choices,
        },
    )


@login_required
@user_passes_test(lambda u: u.is_staff)
def portal_settings(request):
    site = SiteSettings.load()
    if request.method == "POST":
        form = SiteSettingsForm(request.POST, request.FILES, instance=site)
        if form.is_valid():
            form.save()
            messages.success(request, "Site settings updated.")
            return redirect("portal_settings")
    else:
        form = SiteSettingsForm(instance=site)
    return render(request, "portal/settings.html", {"form": form, "site": site})


@login_required
@user_passes_test(lambda u: u.is_staff)
def portal_customers(request):
    customers = Customer.objects.annotate(
        ticket_count=Count("tickets"),
        total_spent=Sum("tickets__total_price"),
    ).order_by("-created_at")
    return render(request, "portal/customers.html", {"customers": customers})


@login_required
@user_passes_test(lambda u: u.is_staff)
def portal_tickets(request):
    tickets = Ticket.objects.select_related("customer", "event", "ticket_type", "payment").order_by("-created_at")
    status = request.GET.get("status")
    if status:
        tickets = tickets.filter(status=status)
    return render(request, "portal/tickets.html", {"tickets": tickets, "active_status": status})


def portal_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("portal_dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if not user.is_staff:
            messages.error(request, "Staff access only.")
        else:
            login(request, user)
            return redirect("portal_dashboard")
    return render(request, "portal/login.html", {"form": form})


def portal_logout(request):
    logout(request)
    return redirect("portal_login")
