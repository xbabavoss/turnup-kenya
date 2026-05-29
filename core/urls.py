from django.urls import path
from . import portal_views, views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("health/sparkpesa/", views.sparkpesa_health, name="sparkpesa_health"),
    path("health/email/", views.email_health, name="email_health"),
    path("", views.home, name="home"),
    path("events/", views.event_list, name="event_list"),
    path("events/<slug:slug>/", views.event_detail, name="event_detail"),
    path("events/<slug:slug>/buy/", views.quick_purchase, name="quick_purchase"),
    path("api/payments/<int:payment_id>/status/", views.payment_status, name="payment_status"),
    path("webhooks/sparkpesa/", views.sparkpesa_webhook, name="sparkpesa_webhook"),
    path("tickets/<uuid:ticket_id>/success/", views.ticket_success, name="ticket_success"),
    path("about/", views.about_page, name="about"),
    path("portal/login/", portal_views.portal_login, name="portal_login"),
    path("portal/logout/", portal_views.portal_logout, name="portal_logout"),
    path("portal/", portal_views.portal_dashboard, name="portal_dashboard"),
    path("portal/events/", portal_views.portal_events, name="portal_events"),
    path("portal/events/save/", portal_views.portal_event_save, name="portal_event_save"),
    path("portal/events/<int:pk>/delete/", portal_views.portal_event_delete, name="portal_event_delete"),
    path("portal/settings/", portal_views.portal_settings, name="portal_settings"),
    path("portal/settings/payments/", portal_views.portal_payments, name="portal_payments"),
    path("portal/customers/", portal_views.portal_customers, name="portal_customers"),
    path("portal/tickets/", portal_views.portal_tickets, name="portal_tickets"),
]
