from .models import SiteSettings


def get_site_settings():
    return SiteSettings.load()
