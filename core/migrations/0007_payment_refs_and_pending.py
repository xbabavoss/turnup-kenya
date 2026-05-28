from django.db import migrations, models


def forwards_initiated_to_pending(apps, schema_editor):
    Payment = apps.get_model("core", "Payment")
    Payment.objects.filter(status="initiated").update(status="pending")


def copy_reference_to_account_reference(apps, schema_editor):
    Payment = apps.get_model("core", "Payment")
    for payment in Payment.objects.all():
        if hasattr(payment, "reference") and payment.reference and not payment.account_reference:
            payment.account_reference = payment.reference
            payment.save(update_fields=["account_reference"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_favicon_svg_sparkpesa"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="account_reference",
            field=models.CharField(
                blank=True,
                help_text="Our reference sent to SparkPesa as accountReference.",
                max_length=120,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="phone_number",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="payment",
            name="sparkpesa_transaction_id",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name="payment",
            name="transaction_ref",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="SparkPesa/M-Pesa reference from callback (empty until paid).",
                max_length=120,
            ),
        ),
        migrations.RunPython(copy_reference_to_account_reference, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="payment",
            name="reference",
        ),
        migrations.AlterField(
            model_name="payment",
            name="account_reference",
            field=models.CharField(
                help_text="Our reference sent to SparkPesa as accountReference.",
                max_length=120,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="payment",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.RunPython(forwards_initiated_to_pending, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name="payment",
            options={"ordering": ["-created_at"]},
        ),
    ]
