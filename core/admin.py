from django.contrib import admin
from .models import Customer, Event, Payment, PromoCode, QRValidationLog, SiteSettings, Ticket, TicketType


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("phone", "email", "full_name", "created_at")
    search_fields = ("phone", "email", "full_name")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "venue", "starts_at", "status", "slots_left", "featured")
    list_filter = ("status", "featured", "category")
    search_fields = ("title", "venue", "location")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TicketTypeInline]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_id", "customer", "event", "attendee_phone", "quantity", "total_price", "status")
    list_filter = ("status", "event")
    search_fields = ("attendee_email", "attendee_phone", "customer__phone")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "account_reference",
        "transaction_ref",
        "method",
        "amount",
        "status",
        "phone_number",
        "created_at",
    )
    search_fields = ("account_reference", "transaction_ref", "sparkpesa_transaction_id")
    list_filter = ("method", "status")


@admin.register(QRValidationLog)
class QRValidationLogAdmin(admin.ModelAdmin):
    list_display = ("ticket", "validator", "was_valid", "message", "created_at")


admin.site.register(PromoCode)
