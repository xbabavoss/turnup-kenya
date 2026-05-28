from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Event, SiteSettings

IMAGE_ACCEPT = "image/jpeg,image/png,image/gif,image/webp,image/svg+xml,.svg"

INPUT = "np-input"
SELECT = "np-select"
TEXTAREA = "np-textarea"


class QuickPurchaseForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": INPUT, "placeholder": "you@email.com"}))
    mpesa_phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "07XX XXX XXX"}),
        label="M-Pesa phone number",
    )
    full_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "Name on ticket (optional)"}),
    )
    quantity = forms.IntegerField(min_value=1, max_value=10, initial=1, widget=forms.HiddenInput())


class PortalEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "title",
            "description",
            "venue",
            "location",
            "category",
            "starts_at",
            "ends_at",
            "poster",
            "ticket_price",
            "available_seats",
            "slots_left",
            "status",
            "featured",
            "lineup",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": INPUT, "placeholder": "Event name"}),
            "description": forms.Textarea(attrs={"class": TEXTAREA, "rows": 3, "placeholder": "Short description"}),
            "venue": forms.TextInput(attrs={"class": INPUT}),
            "location": forms.TextInput(attrs={"class": INPUT}),
            "category": forms.TextInput(attrs={"class": INPUT, "placeholder": "Nightlife"}),
            "starts_at": forms.DateTimeInput(attrs={"class": INPUT, "type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"class": INPUT, "type": "datetime-local"}),
            "poster": forms.FileInput(
                attrs={"class": INPUT, "accept": IMAGE_ACCEPT, "data-image-preview": "event-poster-preview"}
            ),
            "ticket_price": forms.NumberInput(attrs={"class": INPUT, "step": "0.01", "placeholder": "1500"}),
            "available_seats": forms.NumberInput(attrs={"class": INPUT}),
            "slots_left": forms.NumberInput(attrs={"class": INPUT}),
            "status": forms.Select(attrs={"class": SELECT}),
            "lineup": forms.TextInput(attrs={"class": INPUT, "placeholder": "Optional"}),
            "featured": forms.CheckboxInput(attrs={"class": "portal-checkbox"}),
        }

    def clean(self):
        cleaned = super().clean()
        starts = cleaned.get("starts_at")
        ends = cleaned.get("ends_at")
        if starts and ends:
            if ends.date() < starts.date():
                raise ValidationError("End date cannot be before the start date.")
            if ends.date() == starts.date() and ends.time() < starts.time():
                raise ValidationError("On the same day, end time cannot be before start time.")
        return cleaned


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "site_name",
            "tagline",
            "support_email",
            "support_phone",
            "paybill",
            "logo",
            "favicon",
            "hero_image",
            "instagram_url",
            "twitter_url",
            "facebook_url",
            "youtube_url",
            "meta_description",
            "meta_keywords",
        ]
        widgets = {
            "site_name": forms.TextInput(attrs={"class": INPUT}),
            "tagline": forms.Textarea(attrs={"class": TEXTAREA, "rows": 2}),
            "support_email": forms.EmailInput(attrs={"class": INPUT}),
            "support_phone": forms.TextInput(attrs={"class": INPUT}),
            "paybill": forms.TextInput(attrs={"class": INPUT}),
            "logo": forms.FileInput(
                attrs={"class": INPUT, "accept": IMAGE_ACCEPT, "data-image-preview": "site-logo-preview"}
            ),
            "favicon": forms.FileInput(
                attrs={"class": INPUT, "accept": IMAGE_ACCEPT, "data-image-preview": "site-favicon-preview"}
            ),
            "hero_image": forms.FileInput(
                attrs={"class": INPUT, "accept": IMAGE_ACCEPT, "data-image-preview": "site-hero-preview"}
            ),            "instagram_url": forms.URLInput(attrs={"class": INPUT, "placeholder": "https://instagram.com/..."}),
            "twitter_url": forms.URLInput(attrs={"class": INPUT, "placeholder": "https://x.com/..."}),
            "facebook_url": forms.URLInput(attrs={"class": INPUT, "placeholder": "https://facebook.com/..."}),
            "youtube_url": forms.URLInput(attrs={"class": INPUT, "placeholder": "https://youtube.com/..."}),
            "meta_description": forms.Textarea(attrs={"class": TEXTAREA, "rows": 3}),
            "meta_keywords": forms.TextInput(attrs={"class": INPUT}),
        }
