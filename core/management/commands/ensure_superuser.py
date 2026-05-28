import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a staff superuser from environment variables if one does not exist."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()

        if not username or not password:
            self.stdout.write(
                "DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD not set; skipping."
            )
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            updated = []
            if not user.is_staff:
                user.is_staff = True
                updated.append("is_staff")
            if not user.is_superuser:
                user.is_superuser = True
                updated.append("is_superuser")
            if email and user.email != email:
                user.email = email
                updated.append("email")
            if updated:
                user.save(update_fields=updated)
                self.stdout.write(
                    self.style.WARNING(f"Updated existing user '{username}': {', '.join(updated)}.")
                )
            else:
                self.stdout.write(f"Superuser '{username}' already exists.")
            return

        User.objects.create_superuser(
            username=username,
            email=email or f"{username}@turnupkenya.top",
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'."))
