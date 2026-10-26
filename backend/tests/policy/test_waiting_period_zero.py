"""Carência por cobertura: 0 dias é uma escolha explícita («sem carência») e
não pode ser substituída pela carência genérica da regra de elegibilidade."""
from __future__ import annotations

import datetime
from types import SimpleNamespace

from apps.policy.application import issuance_service


def _policy(waiting: dict) -> SimpleNamespace:
    benefits = [
        {"code": code, "contracted": True, "configurationJson": {"waitingDays": {"individual": days}}}
        for code, days in waiting.items()
    ]
    snapshot = SimpleNamespace(snapshot_json={"plan": {"settings": {}, "benefits": benefits}})
    quote = SimpleNamespace(quote_type="NEW", renewal_json={})
    return SimpleNamespace(contracted_terms_snapshot=snapshot, source_quote=quote)


def test_zero_waiting_days_is_kept():
    assert issuance_service._coverage_waiting_days(_policy({"EMERGENCY": 0, "DENTAL": 90})) == {
        "EMERGENCY": 0, "DENTAL": 90,
    }


def test_zero_waiting_days_wins_over_rule_default(monkeypatch):
    policy = _policy({"EMERGENCY": 0, "DENTAL": 90})
    rule_wp = SimpleNamespace(waived_on_verified_portability=False, default_days=30, default_days_by_benefit_category={})
    monkeypatch.setattr(issuance_service, "parse_config", lambda _rule: SimpleNamespace(waiting_period=rule_wp))
    monkeypatch.setattr(issuance_service, "_plan_benefit_codes", lambda _p: ["EMERGENCY", "DENTAL", "PHARMACY"])
    member = SimpleNamespace(rule_version=object(), eligibility_evaluation=None, member_id="m1")
    start = datetime.date(2026, 11, 1)
    ends = issuance_service._waiting_period_ends(policy=policy, policy_member=member, inclusion_date=start)
    assert "EMERGENCY" not in ends  # sem carência
    assert ends["DENTAL"] == "2027-01-30"
    assert ends["PHARMACY"] == "2026-12-01"  # sem valor próprio: carência da regra
