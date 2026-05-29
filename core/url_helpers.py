from django.conf import settings


def absolute_url(request, path: str) -> str:
    """Build https-safe absolute URLs (Railway sits behind a TLS proxy)."""
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return _force_https(path)

    rel = path if path.startswith("/") else f"/{path}"
    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    if base:
        return f"{_force_https(base)}{rel}"

    return _force_https(request.build_absolute_uri(rel))


def _force_https(url: str) -> str:
    on_railway = bool(getattr(settings, "RAILWAY_PUBLIC_DOMAIN", ""))
    if url.startswith("http://") and (on_railway or not settings.DEBUG):
        return "https://" + url[7:]
    return url
