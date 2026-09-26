"""`pricing_run.product_version_id` becomes optional
(DECISIONS_TAKEN.md#S09-POLICY-001, ROADMAP_APOLICES.md Fase 1,
PO-APO-6) — `pricing_run.plan_id` already resolves the product via
`Plan.product_id` (apps.product 0002_plan_direct_to_product). Forward-only
(reverse_sql is a deliberate no-op, same policy as every other migration
in this project).
"""
from django.db import migrations

V027_PRICING_RUN_PRODUCT_VERSION_OPTIONAL = """
ALTER TABLE q360.pricing_run ALTER COLUMN product_version_id DROP NOT NULL;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("pricing", "0002_pricing_engine"),
        ("product", "0002_plan_direct_to_product"),
    ]

    operations = [
        migrations.RunSQL(V027_PRICING_RUN_PRODUCT_VERSION_OPTIONAL, reverse_sql=migrations.RunSQL.noop),
    ]
