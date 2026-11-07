from django.db import migrations


class Migration(migrations.Migration):
    """Junta as migrações de apólices dos dois ramos (pagamentos e merge do colega)."""

    dependencies = [
        ("policy", "0006_merge_20261105_1609"),
        ("policy", "0007_payment_batch"),
    ]
    operations = []
