from django.conf import settings

from .models import SiteSettings
from .url_helpers import absolute_url


def site_settings(request):
    s = SiteSettings.load()
    logo_url = absolute_url(request, s.logo.url) if s.logo else ""
    favicon_url = absolute_url(request, s.favicon.url) if s.favicon else logo_url
    og_image = logo_url
    return {
        "site": s,
        "settings": {
            "site_name": s.site_name,
            "tagline": s.tagline,
            "support_email": s.support_email,
            "support_phone": s.support_phone,
            "paybill": s.paybill,
            "instagram_url": s.instagram_url,
            "twitter_url": s.twitter_url,
            "facebook_url": s.facebook_url,
            "youtube_url": s.youtube_url,
            "meta_description": s.meta_description,
            "meta_keywords": s.meta_keywords,
            "logo_url": logo_url,
            "favicon_url": favicon_url,
            "og_image": og_image,
        },
        "nav_path": request.path,
    }
