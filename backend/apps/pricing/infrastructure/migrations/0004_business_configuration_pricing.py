"""Allow PricingRun to be sourced directly from published Business Configuration.

Existing RatingTable/PricingParameterSet columns remain for backwards compatibility,
but new Quote calculations may use the business_config pricing.* source of truth.
"""
from django.db import migrations


SQL = """
ALTER TABLE q360.pricing_run
    ALTER COLUMN rating_table_id DROP NOT NULL,
    ALTER COLUMN parameter_set_id DROP NOT NULL;

ALTER TABLE q360.pricing_run
    ADD COLUMN IF NOT EXISTS business_configuration_snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE q360.pricing_run
    DROP CONSTRAINT IF EXISTS ck_pricing_versions_present;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("pricing", "0003_product_version_optional"),
        ("business_config", "0001_initial"),
    ]

    operations = [migrations.RunSQL(SQL, reverse_sql=migrations.RunSQL.noop)]
