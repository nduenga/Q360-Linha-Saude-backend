"""R2 — sinistralidade: importação (inclui o histórico de 3 anos na
transferência), indicadores, participação nos resultados e projeção em três
cenários ligada aos cenários de cotação."""
from __future__ import annotations

import io
import uuid
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from tests.quote.conftest import make_client
from tests.quote.test_quote_simulator import _scope

REASON = "Motivo de teste suficiente"
CLAIMS_CSV = "occurrence_date,member_reference,benefit_code,paid_amount,provision_amount\n" + "\n".join(
    f"2025-{month:02d}-15,P{month:03d},{'DENTAL' if month % 2 else 'OUTPATIENT'},80000,{5000 if month == 1 else 0}"
    for month in range(1, 13)
)
PREMIUMS_CSV = "period_start,period_end,premium_amount,insured_count\n2025-01-01,2025-12-31,1200000,10\n"
ASSUMPTIONS = {
    "horizonMonths": 12,
    "targetLossRatioPct": "80",
    "scenarios": {
        "OPTIMISTIC": {"medicalInflationPct": "0", "frequencyTrendPct": "0"},
        "BASE": {"medicalInflationPct": "10", "frequencyTrendPct": "0"},
        "PESSIMISTIC": {"medicalInflationPct": "20", "frequencyTrendPct": "5"},
    },
}


def _upload(client, scope, content, *, kind, name="dados.csv", **extra):
    data = content.encode("utf-8") if isinstance(content, str) else content
    return client.post(
        "/api/v1/claims/imports",
        {"file": SimpleUploadedFile(name, data), "kind": kind, "proposerId": scope["proposerId"], **extra},
        format="multipart",
    )


def _load(client, scope):
    assert _upload(client, scope, CLAIMS_CSV, kind="CLAIMS").status_code == 201
    assert _upload(client, scope, PREMIUMS_CSV, kind="PREMIUMS").status_code == 201


def _summary(client, scope, **query):
    qs = "&".join(f"{k}={v}" for k, v in {"proposerId": scope["proposerId"], **query}.items())
    return client.get(f"/api/v1/claims/summary?{qs}")


# ------------------------------------------------------------------- import
@pytest.mark.django_db
def test_import_claims_and_premiums_with_row_errors(admin_client):
    scope = _scope(admin_client)
    bad = (
        "occurrence_date,benefit_code,paid_amount,provision_amount,currency,status\n"
        "2025-01-10,DENTAL,1000,0,AOA,PAID\n"
        "31/01/2025,OUTPATIENT,\"2500,50\",,AOA,OPEN\n"
        "not-a-date,DENTAL,10,0,AOA,PAID\n"
        "2025-02-01,NO_SUCH_COVER,10,0,AOA,PAID\n"
        "2025-02-02,DENTAL,-5,0,AOA,PAID\n"
        "2025-02-03,DENTAL,5,0,EUR,PAID\n"
        "2025-02-04,DENTAL,5,0,AOA,MAYBE\n"
    )
    dry = _upload(admin_client, scope, bad, kind="CLAIMS", dryRun="true")
    assert dry.status_code == 200 and dry.data["dryRun"] is True
    assert (dry.data["totalRows"], dry.data["importedRows"], dry.data["errorRows"]) == (7, 2, 5)
    assert {e["row"] for e in dry.data["errors"]} == {4, 5, 6, 7, 8}
    assert admin_client.get("/api/v1/claims/imports").data["items"] == []  # dry-run não grava

    policy_id = str(uuid.uuid4())
    real = _upload(admin_client, scope, bad, kind="CLAIMS", source="OTHER_INSURER", policyId=policy_id)
    assert real.status_code == 201 and real.data["importedRows"] == 2
    detail = admin_client.get(f"/api/v1/claims/imports/{real.data['importId']}").data
    assert detail["source"] == "OTHER_INSURER" and detail["errorRows"] == 5 and detail["fileName"] == "dados.csv"
    assert detail["policyId"] == policy_id
    assert len(admin_client.get(f"/api/v1/claims/imports?proposerId={scope['proposerId']}").data["items"]) == 1
    assert len(admin_client.get(f"/api/v1/claims/imports?proposerId={scope['proposerId']}&policyId={policy_id}").data["items"]) == 1
    assert admin_client.get(f"/api/v1/claims/imports?policyId={uuid.uuid4()}").data["items"] == []


@pytest.mark.django_db
def test_import_validation_and_formats(admin_client):
    scope = _scope(admin_client)
    assert _upload(admin_client, scope, "a,b\n1,2\n", kind="CLAIMS").status_code == 400  # faltam colunas
    assert _upload(admin_client, scope, "occurrence_date\n", kind="CLAIMS").status_code == 400  # sem linhas
    assert _upload(admin_client, scope, CLAIMS_CSV, kind="WHATEVER").status_code == 400
    assert _upload(admin_client, scope, CLAIMS_CSV, kind="CLAIMS", source="MARS").status_code == 400
    assert _upload(admin_client, scope, "x", kind="CLAIMS", name="dados.txt").status_code == 400
    ghost = admin_client.post(
        "/api/v1/claims/imports",
        {"file": SimpleUploadedFile("d.csv", CLAIMS_CSV.encode()), "kind": "CLAIMS", "proposerId": str(uuid.uuid4())}, format="multipart",
    )
    assert ghost.status_code == 400
    assert admin_client.post("/api/v1/claims/imports", {"kind": "CLAIMS"}, format="multipart").status_code == 400
    # ponto e vírgula + vírgula decimal + datas dd/mm/aaaa
    semicolon = "occurrence_date;benefit_code;paid_amount\n15/03/2025;DENTAL;1234,50\n"
    assert _upload(admin_client, scope, semicolon, kind="CLAIMS").status_code == 201
    # xlsx
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["period_start", "period_end", "premium_amount", "insured_count"])
    sheet.append(["2025-01-01", "2025-12-31", 1200000, 10])
    buffer = io.BytesIO()
    workbook.save(buffer)
    assert _upload(admin_client, scope, buffer.getvalue(), kind="PREMIUMS", name="premios.xlsx").status_code == 201
    bad_premium = "period_start,period_end,premium_amount,insured_count\n2025-12-31,2025-01-01,10,3\n2025-01-01,2025-12-31,10,0\n"
    result = _upload(admin_client, scope, bad_premium, kind="PREMIUMS", dryRun="true")
    assert result.data["errorRows"] == 2


# ------------------------------------------------------------------ summary
@pytest.mark.django_db
def test_summary_loss_ratio_frequency_and_breakdowns(admin_client):
    scope = _scope(admin_client)
    _load(admin_client, scope)
    data = _summary(admin_client, scope).data
    assert data["historyMonths"] == 12 and data["period"] == {"from": "2025-01-01", "to": "2025-12-31", "months": 12}
    assert data["premium"] == {"earned": "1200000.00", "insuredYears": "10.00"}
    assert data["claims"] == {"count": 12, "paid": "960000.00", "provision": "5000.00", "total": "965000.00",
                              "averageCost": "80416.67", "frequencyPerInsuredYear": "1.20"}
    assert data["lossRatioPct"] == "80.42"
    assert {b["benefitCode"] for b in data["byBenefit"]} == {"DENTAL", "OUTPATIENT"}
    assert data["byBenefit"][0]["benefitCode"] == "DENTAL" and data["byBenefit"][0]["total"] == "485000.00"
    assert [m["month"] for m in data["byMonth"]] == [f"2025-{m:02d}" for m in range(1, 13)]
    assert "pagos + provisões" in data["formulas"]["claims"]

    half = _summary(admin_client, scope, **{"from": "2025-01-01", "to": "2025-06-30"}).data
    assert half["claims"]["count"] == 6 and half["claims"]["total"] == "485000.00"
    # prémio ganho proporcional (181/365 dias do ano)
    assert half["premium"]["earned"] == str((Decimal("1200000") * 181 / 365).quantize(Decimal("0.01")))


@pytest.mark.django_db
def test_rejected_claims_and_other_currencies_do_not_count(admin_client):
    scope = _scope(admin_client)
    _load(admin_client, scope)
    extra = (
        "occurrence_date,benefit_code,paid_amount,status\n"
        "2025-03-01,DENTAL,999999,REJECTED\n"
    )
    _upload(admin_client, scope, extra, kind="CLAIMS")
    assert _summary(admin_client, scope).data["claims"]["total"] == "965000.00"
    usd = "occurrence_date,benefit_code,paid_amount,currency\n2025-03-01,DENTAL,500,USD\n"
    _upload(admin_client, scope, usd, kind="CLAIMS")
    assert _summary(admin_client, scope).data["claims"]["total"] == "965000.00"
    assert _summary(admin_client, scope, currency="USD").data["claims"]["total"] == "500.00"
    assert _summary(admin_client, scope, currency="USD").data["lossRatioPct"] is None  # sem prémio em USD


@pytest.mark.django_db
def test_summary_input_validation_and_empty_history(admin_client):
    scope = _scope(admin_client)
    assert _summary(admin_client, scope).status_code == 400  # nada importado
    _load(admin_client, scope)
    assert _summary(admin_client, scope, **{"from": "2025-06-30", "to": "2025-01-01"}).status_code == 400
    assert _summary(admin_client, scope, **{"from": "junho"}).status_code == 400
    assert admin_client.get("/api/v1/claims/summary").status_code == 400
    assert admin_client.get("/api/v1/claims/summary?proposerId=nope").status_code == 400


@pytest.mark.django_db
def test_claims_are_isolated_per_client(admin_client):
    scope = _scope(admin_client)
    other = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "displayName": "Outro", "registrationNumber": "987654321LA042", "email": "o@example.com", "phone": "+244900000001"},
    ).data["id"]
    _load(admin_client, scope)
    assert _summary(admin_client, {"proposerId": other}).status_code == 400
    _upload(admin_client, {"proposerId": other}, "occurrence_date,benefit_code,paid_amount\n2025-01-01,DENTAL,1\n", kind="CLAIMS")
    assert _summary(admin_client, scope).data["claims"]["count"] == 12


@pytest.mark.django_db
def test_proposer_directory_search_matches_name_email_and_nif(admin_client):
    _scope(admin_client)
    by_name = admin_client.get("/api/v1/proposers?q=Holder")
    by_email = admin_client.get("/api/v1/proposers?q=holder%40example.com")
    by_nif = admin_client.get("/api/v1/proposers?q=123456789LA042")
    assert [item["displayName"] for item in by_name.data["items"]] == ["Holder"]
    assert [item["displayName"] for item in by_email.data["items"]] == ["Holder"]
    assert [item["displayName"] for item in by_nif.data["items"]] == ["Holder"]
    assert admin_client.get("/api/v1/proposers?q=missing").data["items"] == []


# ------------------------------------------------------- profit sharing (PDF)
@pytest.mark.django_db
def test_profit_sharing_when_loss_ratio_is_below_the_agreed_limit(admin_client):
    scope = _scope(admin_client)
    _load(admin_client, scope)
    below = admin_client.get(f"/api/v1/claims/profit-sharing?proposerId={scope['proposerId']}&thresholdPct=85").data
    assert below["eligible"] is True and below["lossRatioPct"] == "80.42" and below["thresholdPct"] == "85.00"
    assert below["refundAmount"] == "54960.00"  # 1.200.000 × (85 − 80,42)/100
    assert below["indicative"] is True and "limite" in below["formula"]
    half_share = admin_client.get(f"/api/v1/claims/profit-sharing?proposerId={scope['proposerId']}&thresholdPct=85&sharePct=50").data
    assert half_share["refundAmount"] == "27480.00"
    above = admin_client.get(f"/api/v1/claims/profit-sharing?proposerId={scope['proposerId']}&thresholdPct=65").data  # exemplo do PDF
    assert above["eligible"] is False and above["refundAmount"] == "0.00"
    configured = admin_client.get(f"/api/v1/claims/profit-sharing?proposerId={scope['proposerId']}").data
    assert configured["thresholdPct"] == "65.00" and configured["sharePct"] == "100.00"
    parameters = admin_client.get("/api/v1/claims/profit-sharing/parameters")
    assert parameters.status_code == 200
    assert parameters.data == {"thresholdPct": "65.00", "sharePct": "100.00"}
    assert admin_client.get(f"/api/v1/claims/profit-sharing?proposerId={scope['proposerId']}&thresholdPct=abc").status_code == 400
    for query in ("thresholdPct=-1", "thresholdPct=101", "sharePct=-1", "sharePct=101", "sharePct=NaN"):
        response = admin_client.get(f"/api/v1/claims/profit-sharing?proposerId={scope['proposerId']}&{query}")
        assert response.status_code == 400, query


# ---------------------------------------------------------------- projection
@pytest.mark.django_db
def test_projection_optimistic_base_and_pessimistic(admin_client):
    scope = _scope(admin_client)
    _load(admin_client, scope)
    run = admin_client.post(
        "/api/v1/claims/projections", {"proposerId": scope["proposerId"], "assumptions": ASSUMPTIONS}, format="json"
    )
    assert run.status_code == 201, run.data
    result = run.data["result"]
    assert result["method"] == "SIMPLE_TREND_V1" and "atuariais" in result["methodNote"]
    assert result["window"] == {"from": "2025-01-01", "to": "2025-12-31", "months": 12} and result["warnings"] == []
    assert result["annualized"] == {"claims": "965000.00", "premium": "1200000.00", "livesScale": "1.0000"}
    scenarios = result["scenarios"]
    assert scenarios["OPTIMISTIC"]["projectedClaims"] == "965000.00" and scenarios["OPTIMISTIC"]["expectedLossRatioPct"] == "80.42"
    assert scenarios["OPTIMISTIC"]["requiredPremium"] == "1206250.00" and scenarios["OPTIMISTIC"]["premiumImpactPct"] == "0.52"
    assert scenarios["BASE"]["projectedClaims"] == "1061500.00" and scenarios["BASE"]["expectedLossRatioPct"] == "88.46"
    assert scenarios["BASE"]["requiredPremium"] == "1326875.00" and scenarios["BASE"]["premiumImpactPct"] == "10.57"
    assert scenarios["PESSIMISTIC"]["projectedClaims"] == "1215900.00" and scenarios["PESSIMISTIC"]["expectedLossRatioPct"] == "101.32"
    assert scenarios["PESSIMISTIC"]["premiumImpactPct"] == "26.66"
    assert len(scenarios["BASE"]["monthly"]) == 12 and scenarios["BASE"]["monthly"][0]["month"] == 1
    assert Decimal(scenarios["OPTIMISTIC"]["premiumImpactPct"]) < Decimal(scenarios["BASE"]["premiumImpactPct"]) < Decimal(scenarios["PESSIMISTIC"]["premiumImpactPct"])
    fetched = admin_client.get(f"/api/v1/claims/projections/{run.data['id']}").data
    assert fetched["result"] == result and fetched["assumptions"]["targetLossRatioPct"] == "80"
    assert len(admin_client.get(f"/api/v1/claims/projections?proposerId={scope['proposerId']}").data["items"]) == 1


@pytest.mark.django_db
def test_projection_scales_with_the_projected_population(admin_client):
    scope = _scope(admin_client)
    _load(admin_client, scope)
    run = admin_client.post(
        "/api/v1/claims/projections",
        {"proposerId": scope["proposerId"], "assumptions": {**ASSUMPTIONS, "projectedInsured": 20}}, format="json",
    ).data["result"]
    assert run["annualized"] == {"claims": "1930000.00", "premium": "2400000.00", "livesScale": "2.0000"}
    assert run["scenarios"]["BASE"]["expectedLossRatioPct"] == "88.46"  # mix de vidas não muda o rácio


@pytest.mark.django_db
def test_projection_with_short_history_warns(admin_client):
    scope = _scope(admin_client)
    _upload(admin_client, scope, "occurrence_date,benefit_code,paid_amount\n2025-01-10,DENTAL,10000\n2025-03-10,DENTAL,20000\n", kind="CLAIMS")
    _upload(admin_client, scope, "period_start,period_end,premium_amount,insured_count\n2025-01-01,2025-03-31,300000,10\n", kind="PREMIUMS")
    run = admin_client.post("/api/v1/claims/projections", {"proposerId": scope["proposerId"], "assumptions": ASSUMPTIONS}, format="json").data
    assert run["result"]["window"]["months"] == 3
    assert any("Menos de 12 meses" in w for w in run["result"]["warnings"])
    assert run["result"]["annualized"]["claims"] == "120000.00"


@pytest.mark.django_db
def test_projection_assumption_validation(admin_client):
    scope = _scope(admin_client)
    _load(admin_client, scope)

    def run(assumptions):
        return admin_client.post("/api/v1/claims/projections", {"proposerId": scope["proposerId"], "assumptions": assumptions}, format="json")

    scenarios = ASSUMPTIONS["scenarios"]
    bad_cases = [
        {**ASSUMPTIONS, "horizonMonths": 0},
        {**ASSUMPTIONS, "horizonMonths": "12"},
        {**ASSUMPTIONS, "targetLossRatioPct": "0"},
        {**ASSUMPTIONS, "targetLossRatioPct": "150"},
        {**ASSUMPTIONS, "extra": 1},
        {**ASSUMPTIONS, "scenarios": {"BASE": scenarios["BASE"]}},  # sem valores por omissão
        {**ASSUMPTIONS, "scenarios": {**scenarios, "OPTIMISTIC": {"medicalInflationPct": "30", "frequencyTrendPct": "0"}}},  # otimista > base
        {**ASSUMPTIONS, "scenarios": {**scenarios, "BASE": {"medicalInflationPct": "abc", "frequencyTrendPct": "0"}}},
        {**ASSUMPTIONS, "projectedInsured": 0},
    ]
    for case in bad_cases:
        assert run(case).status_code == 400, case
    assert admin_client.post("/api/v1/claims/projections", {"proposerId": scope["proposerId"]}, format="json").status_code == 400
    assert run(None).status_code == 400
    # sem prémio importado não há projeção
    other = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "INDIVIDUAL", "displayName": "Sem prémio", "registrationNumber": "111222333LA042", "email": "s@example.com", "phone": "+244900000002"},
    ).data["id"]
    _upload(admin_client, {"proposerId": other}, "occurrence_date,benefit_code,paid_amount\n2025-01-01,DENTAL,1\n", kind="CLAIMS")
    resp = admin_client.post("/api/v1/claims/projections", {"proposerId": other, "assumptions": ASSUMPTIONS}, format="json")
    assert resp.status_code == 400 and "premium" in resp.data["detail"]


@pytest.mark.django_db
def test_assumption_sets_are_saved_and_reused(admin_client):
    scope = _scope(admin_client)
    _load(admin_client, scope)
    created = admin_client.post("/api/v1/claims/assumption-sets", {"name": "Premissas 2026", "assumptions": ASSUMPTIONS}, format="json")
    assert created.status_code == 201 and created.data["assumptions"]["horizonMonths"] == 12
    assert admin_client.post("/api/v1/claims/assumption-sets", {"name": "Premissas 2026", "assumptions": ASSUMPTIONS}, format="json").status_code == 409
    assert admin_client.post("/api/v1/claims/assumption-sets", {"name": "Inválidas", "assumptions": {"horizonMonths": 1}}, format="json").status_code == 400
    assert [s["name"] for s in admin_client.get("/api/v1/claims/assumption-sets").data] == ["Premissas 2026"]
    assert admin_client.get(f"/api/v1/claims/assumption-sets/{created.data['id']}").status_code == 200
    run = admin_client.post(
        "/api/v1/claims/projections", {"proposerId": scope["proposerId"], "assumptionSetId": created.data["id"]}, format="json"
    )
    assert run.status_code == 201 and run.data["assumptionSetId"] == created.data["id"]
    filtered = admin_client.get(f"/api/v1/claims/projections?proposerId={scope['proposerId']}&policyId={uuid.uuid4()}")
    assert filtered.status_code == 200 and filtered.data["items"] == []
    assert admin_client.post("/api/v1/claims/projections", {"proposerId": scope["proposerId"], "assumptionSetId": str(uuid.uuid4())}, format="json").status_code == 404


# ----------------------------------------------------- ligação à cotação (R5)
@pytest.mark.django_db
def test_projection_is_attached_to_a_scenario_and_shown_in_the_comparison(admin_client):
    scope = _scope(admin_client)
    _load(admin_client, scope)
    run = admin_client.post("/api/v1/claims/projections", {"proposerId": scope["proposerId"], "assumptions": ASSUMPTIONS}, format="json").data
    base = admin_client.post(f"/api/v1/quotes/{scope['quoteId']}/scenarios", {"name": "Sem agravamento"}, format="json").data
    with_projection = admin_client.post(
        f"/api/v1/quotes/{scope['quoteId']}/scenarios",
        {"name": "Pessimista", "parameters": {"adjustments": [{"kind": "SURCHARGE_PERCENT", "value": "26.66"}],
                                               "projection": {"projectionRunId": run["id"], "scenario": "PESSIMISTIC"}}},
        format="json",
    )
    assert with_projection.status_code == 201, with_projection.data
    assert with_projection.data["parameters"]["projection"] == {
        "projectionRunId": run["id"], "scenario": "PESSIMISTIC", "expectedLossRatioPct": "101.32", "premiumImpactPct": "26.66"}
    compare = admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/scenarios/compare").data
    by_name = {s["name"]: s for s in compare["scenarios"]}
    assert by_name["Pessimista"]["projection"]["expectedLossRatioPct"] == "101.32" and by_name["Sem agravamento"]["projection"] is None
    assert base["id"]

    bad = admin_client.post(
        f"/api/v1/quotes/{scope['quoteId']}/scenarios",
        {"name": "X", "parameters": {"projection": {"projectionRunId": str(uuid.uuid4()), "scenario": "BASE"}}}, format="json",
    )
    assert bad.status_code == 400
    wrong_scenario = admin_client.post(
        f"/api/v1/quotes/{scope['quoteId']}/scenarios",
        {"name": "Y", "parameters": {"projection": {"projectionRunId": run["id"], "scenario": "NOPE"}}}, format="json",
    )
    assert wrong_scenario.status_code == 400


@pytest.mark.django_db
def test_quote_claims_context_and_three_year_history_requirement(admin_client):
    group = {"segment": "GROUP", "tier": "CUSTOM", "accessSystem": "MIXED", "group": {"minInsured": 1, "adhesion": "MANDATORY"}}
    scope = _scope(admin_client, settings=group)
    context = admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/claims-context").data
    assert context["available"] is False and context["threeYearsAvailable"] is False
    history = next(i for i in admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/requirements").data["info"] if i["code"] == "CLAIMS_HISTORY_ON_TRANSFER")
    assert history["satisfied"] is False and history["monthsAvailable"] == 0

    _upload(admin_client, scope, "period_start,period_end,premium_amount,insured_count\n2023-01-01,2025-12-31,3600000,10\n", kind="PREMIUMS", source="OTHER_INSURER")
    _upload(admin_client, scope, "occurrence_date,benefit_code,paid_amount\n2023-02-01,DENTAL,100\n", kind="CLAIMS", source="OTHER_INSURER")
    context = admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/claims-context").data
    assert context["available"] is True and context["historyMonths"] == 36 and context["threeYearsAvailable"] is True
    history = next(i for i in admin_client.get(f"/api/v1/quotes/{scope['quoteId']}/requirements").data["info"] if i["code"] == "CLAIMS_HISTORY_ON_TRANSFER")
    assert history["satisfied"] is True and history["monthsAvailable"] == 36


# ------------------------------------------------------- privacidade / acesso
@pytest.mark.django_db
def test_health_data_access_is_restricted_and_reads_are_audited(admin_client, tenant):
    scope = _scope(admin_client)
    _load(admin_client, scope)
    subscriber = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read q360.write", actor_id="sub-1")
    assert subscriber.get(f"/api/v1/claims/summary?proposerId={scope['proposerId']}").status_code == 403  # sem audit:read
    assert subscriber.get("/api/v1/claims/imports").status_code == 403
    assert subscriber.get(f"/api/v1/quotes/{scope['quoteId']}/claims-context").status_code == 403

    auditor = make_client(tenant_id=tenant.id, roles=["SUBSCRIPTION_MANAGER"], scope="q360.read q360.audit", actor_id="aud-1")
    assert auditor.get(f"/api/v1/claims/summary?proposerId={scope['proposerId']}").status_code == 200
    assert _upload(auditor, scope, CLAIMS_CSV, kind="CLAIMS").status_code == 403  # só gere quem tem pricing-config:manage
    assert auditor.post("/api/v1/claims/assumption-sets", {"name": "x", "assumptions": ASSUMPTIONS}, format="json").status_code == 403

    events = auditor.get("/api/v1/audit-events?action=claims.summary_viewed").data["items"]
    assert events and events[0]["actorId"] in ("aud-1", "actor-1") and events[0]["entityId"] == scope["proposerId"]
    imported = auditor.get("/api/v1/audit-events?action=claims.imported").data["items"]
    assert {e["metadata"]["after"]["kind"] for e in imported} == {"CLAIMS", "PREMIUMS"}
    # nenhuma linha individual sai da API
    body = str(auditor.get(f"/api/v1/claims/summary?proposerId={scope['proposerId']}").data)
    assert "P001" not in body and "member_reference" not in body


@pytest.mark.django_db
def test_methodology_is_labelled_indicative_and_template_matches_the_import(admin_client):
    meta = admin_client.get("/api/v1/claims/methodology")
    assert meta.status_code == 200, meta.data
    assert meta.data["method"] == "SIMPLE_TREND_V1" and meta.data["indicative"] is True
    assert meta.data["importFormats"]["CLAIMS"]["required"] == ["occurrence_date", "benefit_code", "paid_amount"]
    template = admin_client.get("/api/v1/claims/import-template?kind=PREMIUMS")
    assert template.status_code == 200 and "text/csv" in template["Content-Type"]
    header = template.content.decode().splitlines()[0].split(",")
    assert header[:3] == ["period_start", "period_end", "premium_amount"]
    assert admin_client.get("/api/v1/claims/import-template?kind=NOPE").status_code == 400
