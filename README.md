# NightPulse - Premium Event Ticketing Platform

A Django-based premium event ticketing platform inspired by Eventbrite-class UX and African nightlife culture.

## Features Included

- Django auth with register/login and user dashboard
- Event listing and single event detail pages
- Checkout flow with M-Pesa/card payment structure
- Automatic ticket generation with unique QR + PDF
- Email confirmation with premium dark HTML template
- Admin analytics dashboard and QR scan validation page
- Dark-mode, neon-accent premium UI (mobile-first)

## Quick Start

1. Create and activate virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy env values:
   - `copy .env.example .env`
4. Run migrations:
   - `python manage.py migrate`
5. Create superuser:
   - `python manage.py createsuperuser`
6. Start dev server:
   - `python manage.py runserver`

## Production Notes

- Switch to PostgreSQL by setting `DB_ENGINE=postgresql`.
- Replace `process_payment` in `core/services.py` with real M-Pesa STK push and card gateway APIs.
- Replace console email backend with SMTP/SendGrid/Postmark.
- Add Celery + Redis for background email and payment callbacks.
