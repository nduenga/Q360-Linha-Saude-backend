"""`quote.product_version_id`/`quote_snapshot.product_version_id` become
optional (DECISIONS_TAKEN.md#S09-POLICY-001, ROADMAP_APOLICES.md Fase 1,
PO-APO-6). Both tables already carry `plan_id` directly (0001_quote_
baseline.py), and `Plan` now carries `product_id` directly
(apps.product 0002_plan_direct_to_product) — nothing downstream needs
`product_version_id` to resolve a Quote's product any more. The column is
kept (not dropped) for now; new code simply stops writing it. Forward-only
(reverse_sql is a deliberate no-op, same policy as every other migration
in this project).
"""
from django.db import migrations

V026_QUOTE_PRODUCT_VERSION_OPTIONAL = """
ALTER TABLE q360.quote ALTER COLUMN product_version_id DROP NOT NULL;
ALTER TABLE q360.quote_snapshot ALTER COLUMN product_version_id DROP NOT NULL;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("quote", "0003_documents_and_numbering"),
        ("product", "0002_plan_direct_to_product"),
    ]

    operations = [
        migrations.RunSQL(V026_QUOTE_PRODUCT_VERSION_OPTIONAL, reverse_sql=migrations.RunSQL.noop),
    ]
