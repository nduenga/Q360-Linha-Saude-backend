from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.business_config.application.pricing import (
    PublishedBusinessPricing,
    resolve_factors,
    resolve_reference_premium,
)
from apps.pricing.domain.errors import PricingConfigError


def _pricing():
    return PublishedBusinessPricing(
        reference_premiums={
            "currency_code": "AOA",
            "premiums": [
                {"age_from": 18, "age_to": 35, "plan": "BASE", "annual_premium": "100000"},
                {"age_from": 36, "age_to": 50, "plan": "BASE", "annual_premium": "150000"},
            ],
        },
        factors={
            "factors": [
                {"code": "ACCESS_NETWORK", "dimension": "accessSystem", "condition": "NETWORK", "factor": "1.10"},
                {"code": "TIER_BASE", "dimension": "tier", "condition": "BASE", "factor": "1.00"},
            ]
        },
        adjustments={"rules": []},
        taxes_fees={"charges": []},
        versions={},
    )


def test_reference_premium_is_resolved_from_plan_and_age():
    plan = SimpleNamespace(code="BASE", name="Plano Base")
    assert resolve_reference_premium(pricing=_pricing(), plan=plan, age=40) == Decimal("150000")


def test_reference_premium_rejects_ambiguous_ranges():
    pricing = _pricing()
    pricing = PublishedBusinessPricing(
        reference_premiums={
            "currency_code": "AOA",
            "premiums": pricing.reference_premiums["premiums"] + [
                {"age_from": 36, "age_to": 50, "plan": "BASE", "annual_premium": "160000"}
            ],
        },
        factors=pricing.factors,
        adjustments=pricing.adjustments,
        taxes_fees=pricing.taxes_fees,
        versions={},
    )
    with pytest.raises(PricingConfigError):
        resolve_reference_premium(pricing=pricing, plan=SimpleNamespace(code="BASE", name="Base"), age=40)


def test_factor_uses_configured_dimension_and_condition():
    result = resolve_factors(
        pricing=_pricing(),
        context={"accessSystem": "NETWORK", "tier": "BASE"},
    )
    assert [x["code"] for x in result] == ["ACCESS_NETWORK", "TIER_BASE"]
    assert result[0]["factor"] == Decimal("1.10")
