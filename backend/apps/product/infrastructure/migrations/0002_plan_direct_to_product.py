"""Plan links directly to Product; ProductVersion retired from the data
model (DECISIONS_TAKEN.md#S09-POLICY-001, ROADMAP_APOLICES.md Fase 1 —
Product Owner decision PO-APO-6, 2026-09-26: "deixam de existir versões de
produto na plataforma; só produtos e planos").

This is step 1 ("aditivo") of the 2-step migration the roadmap calls for:
add `plan.product_id`, backfill it from the Plan's current
`product_version.product_id`, then make it NOT NULL. `plan.product_version_id`
becomes nullable (application code stops writing it) but is NOT dropped
yet — a follow-up migration drops it, and the `product_version` table
itself, once this step has run in every environment. Forward-only, same
policy as every other migration in this project (see
0001_product_baseline.py's own `reverse_sql` docstring) — `reverse_sql` is
a deliberate no-op.
"""
from django.db import migrations

V025_PLAN_DIRECT_TO_PRODUCT = """
ALTER TABLE q360.plan ADD COLUMN product_id uuid REFERENCES q360.product(id);

UPDATE q360.plan p
SET product_id = pv.product_id
FROM q360.product_version pv
WHERE p.product_version_id = pv.id;

ALTER TABLE q360.plan ALTER COLUMN product_id SET NOT NULL;
ALTER TABLE q360.plan ALTER COLUMN product_version_id DROP NOT NULL;
"""


class Migration(migrations.Migration):
    dependencies = [("product", "0001_product_baseline")]

    operations = [
        migrations.RunSQL(V025_PLAN_DIRECT_TO_PRODUCT, reverse_sql=migrations.RunSQL.noop),
    ]
