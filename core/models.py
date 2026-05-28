import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

from .validators import validate_image_file


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SiteSettings(TimeStampedModel):
    site_name = models.CharField(max_length=120, default="Turn Up Kenya")
    tagline = models.TextField(
        default="Book tickets to concerts, nightlife and culture events across Kenya."
    )
    support_email = models.EmailField(default="hello@turnupkenya.com")
    support_phone = models.CharField(max_length=30, default="+254 700 000 000")
    paybill = models.CharField(max_length=20, default="123456")
    logo = models.FileField(
        upload_to="site/", blank=True, null=True, validators=[validate_image_file]
    )
    favicon = models.FileField(
        upload_to="site/",
        blank=True,
        null=True,
        validators=[validate_image_file],
        help_text="Site favicon (PNG, JPG, or SVG).",
    )
    hero_image = models.FileField(
        upload_to="site/",
        blank=True,
        null=True,
        validators=[validate_image_file],
        help_text="Home page hero background image.",
    )
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    meta_description = models.TextField(
        blank=True,
        default="Turn Up Kenya. Book event tickets online with M-Pesa. Instant QR passes for parties, concerts and festivals.",
    )
    meta_keywords = models.CharField(
        max_length=255,
        blank=True,
        default="Turn Up Kenya, event tickets, M-Pesa tickets, Nairobi events, concerts, nightlife",
    )

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Customer(TimeStampedModel):
    phone = models.CharField(max_length=20, unique=True, db_index=True)
    email = models.EmailField()
    full_name = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.phone


class Event(TimeStampedModel):
    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        SOLD_OUT = "sold_out", "Sold Out"
        LIVE = "live", "Live"
        ENDED = "ended", "Ended"

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    venue = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    poster = models.FileField(
        upload_to="events/posters/", blank=True, null=True, validators=[validate_image_file]
    )
    banner = models.FileField(
        upload_to="events/banners/", blank=True, null=True, validators=[validate_image_file]
    )
    available_seats = models.PositiveIntegerField(default=0)
    slots_left = models.PositiveIntegerField(default=0, help_text="Remaining tickets available")
    category = models.CharField(max_length=50, default="Nightlife")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPCOMING)
    featured = models.BooleanField(default=False)
    lineup = models.TextField(blank=True, help_text="Comma separated DJs/artists")
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.slots_left == 0 and self.available_seats:
            self.slots_left = self.available_seats
        super().save(*args, **kwargs)
        self.ensure_default_ticket()

    def ensure_default_ticket(self):
        tt = self.ticket_types.first()
        if not tt:
            TicketType.objects.create(
                event=self,
                name="General Admission",
                price=self.ticket_price,
                quantity=self.available_seats or self.slots_left or 100,
                description="Standard entry",
            )
        else:
            tt.price = self.ticket_price
            tt.save(update_fields=["price"])

    @property
    def seats_left(self):
        return self.slots_left


class TicketType(TimeStampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    is_vip = models.BooleanField(default=False)
    early_bird = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.event.title} - {self.name}"


class PromoCode(TimeStampedModel):
    code = models.CharField(max_length=40, unique=True)
    discount_percent = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.code

    def is_valid(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class Ticket(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"
        USED = "used", "Used"

    ticket_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="tickets", null=True, blank=True
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tickets")
    ticket_type = models.ForeignKey(TicketType, on_delete=models.PROTECT, related_name="tickets")
    attendee_name = models.CharField(max_length=150)
    attendee_email = models.EmailField()
    attendee_phone = models.CharField(max_length=20, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    qr_token = models.CharField(max_length=255, blank=True)
    qr_image = models.ImageField(upload_to="tickets/qr/", blank=True, null=True)
    pdf_ticket = models.FileField(upload_to="tickets/pdf/", blank=True, null=True)
    scanned_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.attendee_phone or self.customer.phone} - {self.event.title}"


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        MPESA = "mpesa", "M-Pesa"
        CARD = "card", "Card"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="payment")
    method = models.CharField(max_length=20, choices=Method.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    phone_number = models.CharField(max_length=20, blank=True)
    account_reference = models.CharField(
        max_length=120,
        unique=True,
        help_text="Our reference sent to SparkPesa as accountReference.",
    )
    transaction_ref = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
        help_text="SparkPesa/M-Pesa reference from callback (empty until paid).",
    )
    sparkpesa_transaction_id = models.CharField(max_length=64, blank=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        label = self.transaction_ref or self.account_reference
        return f"{label} ({self.status})"


class QRValidationLog(TimeStampedModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="validation_logs")
    validator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    was_valid = models.BooleanField(default=False)
    message = models.CharField(max_length=255)
    scanned_payload = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.ticket.ticket_id} - {self.was_valid}"
