# Deploy Turn Up Kenya on Railway

## 1. Create project

1. Push this repo to GitHub.
2. In [Railway](https://railway.com), **New Project** → **Deploy from GitHub repo** → select this repository.
3. Railway detects Python via Nixpacks (`runtime.txt`, `requirements.txt`).

## 2. Add PostgreSQL

1. In the project, **+ New** → **Database** → **PostgreSQL**.
2. Railway sets `DATABASE_URL` on your web service automatically (link the variable if needed).

## 3. Configure variables

In the **web service** → **Variables**, set (see `.env.railway.example`):

| Variable | Required | Notes |
|----------|----------|--------|
| `SECRET_KEY` | Yes | Long random string |
| `DEBUG` | Yes | `False` in production |
| `SITE_URL` | Yes | `https://<your-app>.up.railway.app` after deploy |
| `ALLOWED_HOSTS` | Yes | Same hostname without `https://` |
| `CSRF_TRUSTED_ORIGINS` | Yes | Full `https://` URL |
| `RESEND_API_KEY` | Yes (prod) | [Resend](https://resend.com) — SMTP is blocked from Railway |
| `RESEND_FROM_EMAIL` | Yes | e.g. `Turn Up Kenya <tickets@turnupkenya.top>` after domain verify |
| `EMAIL_*` | Optional | SMTP fallback (local dev only; times out on Railway) |
| `SPARKPESA_*` | Yes | M-Pesa credentials |
| `SPARKPESA_CALLBACK_URL` | Recommended | `{SITE_URL}/webhooks/sparkpesa/` |
| `DJANGO_SUPERUSER_USERNAME` | Yes | Portal login username |
| `DJANGO_SUPERUSER_PASSWORD` | Yes | Portal login password |
| `DJANGO_SUPERUSER_EMAIL` | Optional | Admin email |

`DATABASE_URL` is injected by the Postgres plugin.

On each deploy, `ensure_superuser` creates the admin account if missing (safe to re-run).

Optional: leave `SITE_URL` empty and rely on `RAILWAY_PUBLIC_DOMAIN` (set automatically by Railway).

## 4. Build & deploy

Railway runs (from `railway.toml`):

- **Pre-deploy:** `migrate` + `collectstatic`
- **Start:** Gunicorn on `$PORT`

Health check path: `/health/`

## 5. After first deploy

1. Copy your public URL from **Settings → Networking**.
2. Update `SITE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `SPARKPESA_CALLBACK_URL`.
3. Register the webhook URL in SparkPesa: `https://<domain>/webhooks/sparkpesa/`
4. Open `/portal/login/` and sign in with `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD`.

   To create another admin manually:

   ```bash
   railway run python manage.py createsuperuser
   ```

## 6. Persistent media (Railway Volume)

Uploaded files (logos, posters, tickets) are **not** in Git. Without a volume, they are wiped on every deploy.

### Where to create a volume (not under Settings)

Railway moved volumes out of the service Settings tab. Use either:

1. **Command Palette:** open your project → press **`Ctrl+K`** (Windows) or **`Cmd+K`** (Mac) → type **“Volume”** → **Create Volume**.
2. **Project canvas:** **right‑click** empty space on the architecture view → add a volume.
3. **CLI:** `railway volume add --mount-path /app/media`

When prompted:

- **Service:** your web app (not Postgres)
- **Mount path:** `/app/media` (matches Django `MEDIA_ROOT`)

Railway injects `RAILWAY_VOLUME_MOUNT_PATH` at runtime; the app uses that automatically.

**Notes:**

- Volumes mount when the **container starts**, not during build/pre-deploy.
- After attaching the volume, **re-upload** logos/posters once on production.
- Free plan: **1 volume per project**.

### HTTPS / favicon

Set `SITE_URL=https://your-app.up.railway.app` (with **https**). The app forces HTTPS for logo/favicon/OG URLs on Railway.

Ensure `DEBUG=False` in production variables.

## 7. Local production smoke test

```bash
pip install -r requirements.txt
set DEBUG=False
set DATABASE_URL=postgres://...
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```
