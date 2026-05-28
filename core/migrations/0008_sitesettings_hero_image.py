import core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_payment_refs_and_pending"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="hero_image",
            field=models.FileField(
                blank=True,
                help_text="Home page hero background image.",
                null=True,
                upload_to="site/",
                validators=[core.validators.validate_image_file],
            ),
        ),
    ]
