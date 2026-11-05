from __future__ import annotations

import datetime
import uuid

import pytest
from django.utils import timezone

from apps.client.infrastructure.models import Proposer
from apps.policy.infrastructure.models import Policy
from apps.product.infrastructure.models import Benefit, Plan, PlanBenefit, Product
from apps.quote.infrastructure.models import Quote, QuoteSnapshot
from tests.foundation.conftest import make_client


@pytest.mark.django_db
def test_report_endpoints_return_tenant_report_data(admin_client, tenant):
    product = Product.all_tenants.create(
        tenant_id=tenant.id,
        code=f"REPORT-{uuid.uuid4().hex[:8]}",
        name="Produto de relatório",
    )
    plan = Plan.all_tenants.create(
        tenant_id=tenant.id,
        product_id=product.id,
        code=f"PLAN-{uuid.uuid4().hex[:8]}",
        name="Plano de relatório",
    )
    proposer = Proposer.all_tenants.create(
        tenant_id=tenant.id,
        proposer_type="INDIVIDUAL",
        display_name="Empresa de relatório",
        nif=f"{int(uuid.uuid4().hex[:8], 16) % 1_000_000_000:09d}LA042",
        date_of_birth=datetime.date(1985, 1, 1),
        registration_number=f"REPORT-{uuid.uuid4().hex[:8]}",
    )
    today = timezone.localdate()
    bound_quote = Quote.all_tenants.create(
        tenant_id=tenant.id,
        proposer_id=proposer.id,
        plan_id=plan.id,
        status="BOUND",
        created_by="test",
    )
    Quote.all_tenants.create(
        tenant_id=tenant.id,
        proposer_id=proposer.id,
        plan_id=plan.id,
        status="DRAFT",
        created_by="test",
    )
    benefit = Benefit.all_tenants.create(
        tenant_id=tenant.id,
        code=f"BEN-{uuid.uuid4().hex[:8]}",
        name="Cobertura de relatório",
        benefit_type="BASE",
    )
    PlanBenefit.all_tenants.create(
        tenant_id=tenant.id,
        plan_id=plan.id,
        benefit_id=benefit.id,
    )
    snapshot = QuoteSnapshot.all_tenants.create(
        tenant_id=tenant.id,
        quote_id=bound_quote.id,
        snapshot_no=1,
        snapshot_type="APPROVAL",
        plan_id=plan.id,
        snapshot_json={},
        checksum="report-test",
        created_by="test",
    )
    Policy.all_tenants.create(
        tenant_id=tenant.id,
        policy_number=f"POL-{uuid.uuid4().hex[:8]}",
        source_quote_id=bound_quote.id,
        contracted_terms_snapshot_id=snapshot.id,
        proposer_id=proposer.id,
        plan_id=plan.id,
        policy_type="GROUP",
        term_months=12,
        start_date=today,
        end_date=today + datetime.timedelta(days=364),
        status="ACTIVE",
        payment_frequency="ANUAL",
        currency_code="AOA",
        issued_by="test",
    )

    date_filter = {"from": today.isoformat(), "to": today.isoformat()}
    products = admin_client.get("/api/v1/reports/top-products", date_filter)
    coverages = admin_client.get("/api/v1/reports/top-coverages", date_filter)
    issuance = admin_client.get("/api/v1/reports/issuance", date_filter)

    assert products.status_code == 200
    assert products.data == [
        {
            "productId": str(product.id),
            "productName": "Produto de relatório",
            "quoteCount": 2,
            "issuedCount": 1,
        }
    ]
    assert coverages.status_code == 200
    assert coverages.data == [
        {
            "benefitId": str(benefit.id),
            "benefitName": "Cobertura de relatório",
            "category": "BASE",
            "planCount": 1,
        }
    ]
    assert issuance.status_code == 200
    assert issuance.data == {
        "totalQuotes": 2,
        "totalPolicies": 1,
        "quotesByStatus": [{"status": "BOUND", "count": 1}, {"status": "DRAFT", "count": 1}],
        "policiesByStatus": [{"status": "ACTIVE", "count": 1}],
    }


@pytest.mark.django_db
def test_reports_reject_invalid_or_reversed_date_filters(admin_client):
    invalid = admin_client.get("/api/v1/reports/top-products", {"from": "not-a-date"})
    assert invalid.status_code == 400
    reversed_range = admin_client.get(
        "/api/v1/reports/issuance",
        {"from": "2026-11-02", "to": "2026-11-01"},
    )
    assert reversed_range.status_code == 400
    assert any(error["field"] == "to" for error in reversed_range.data["fieldErrors"])


@pytest.mark.django_db
def test_reports_require_audit_scope(tenant):
    read_client = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read")
    response = read_client.get("/api/v1/reports/issuance")
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("slug", "title"),
    [
        ("top-products", "Produtos mais cotados"),
        ("top-coverages", "Coberturas mais procuradas"),
        ("issuance", "Cotações e apólices emitidas"),
    ],
)
def test_report_pdf_is_a_readable_download(admin_client, slug, title):
    import io

    from pypdf import PdfReader

    response = admin_client.get(f"/api/v1/reports/{slug}/pdf?from=2026-01-01&to=2026-12-31")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "attachment" in response["Content-Disposition"]
    text = PdfReader(io.BytesIO(response.content)).pages[0].extract_text()
    assert title in text
    assert "01/01/2026 a 31/12/2026" in text


@pytest.mark.django_db
def test_report_pdf_shows_the_same_rows_as_the_screen(admin_client, tenant):
    import io

    from pypdf import PdfReader

    product = Product.all_tenants.create(tenant_id=tenant.id, code=f"PDF-{uuid.uuid4().hex[:8]}", name="Produto PDF")
    plan = Plan.all_tenants.create(tenant_id=tenant.id, product_id=product.id, code=f"P-{uuid.uuid4().hex[:8]}", name="Plano")
    proposer = Proposer.all_tenants.create(
        tenant_id=tenant.id, proposer_type="INDIVIDUAL", display_name="Cliente", date_of_birth=datetime.date(1985, 1, 1),
        nif=f"{int(uuid.uuid4().hex[:8], 16) % 1_000_000_000:09d}LA042", registration_number=f"R-{uuid.uuid4().hex[:8]}",
    )
    Quote.all_tenants.create(
        tenant_id=tenant.id, proposer_id=proposer.id, plan_id=plan.id, status="DRAFT", created_by="test",
    )
    response = admin_client.get("/api/v1/reports/top-products/pdf")
    assert response.status_code == 200, response.content[:200]
    text = PdfReader(io.BytesIO(response.content)).pages[0].extract_text()
    assert "Produto PDF" in text and "Todo o período" in text


@pytest.mark.django_db
def test_report_pdf_rejects_an_unknown_report_and_needs_the_audit_scope(admin_client, tenant):
    assert admin_client.get("/api/v1/reports/desconhecido/pdf").status_code == 404
    reader = make_client(tenant_id=tenant.id, roles=["UNDERWRITER"], scope="q360.read")
    assert reader.get("/api/v1/reports/top-products/pdf").status_code == 403


@pytest.mark.django_db
def test_report_pdf_shows_the_time_in_luanda(admin_client):
    import io
    from unittest import mock

    from pypdf import PdfReader

    moment = datetime.datetime(2026, 11, 5, 23, 30, tzinfo=datetime.timezone.utc)
    with mock.patch("apps.foundation.application.report_pdf.timezone.now", return_value=moment):
        response = admin_client.get("/api/v1/reports/issuance/pdf")
    assert "06/11/2026, 00:30" in PdfReader(io.BytesIO(response.content)).pages[0].extract_text()


def _excel_rows(response):
    import io

    import openpyxl

    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    return [[cell for cell in row if cell is not None] for row in sheet.iter_rows(values_only=True)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("slug", "title", "filename"),
    [
        ("top-products", "Produtos mais cotados", "produtos-mais-cotados.xlsx"),
        ("top-coverages", "Coberturas mais procuradas", "coberturas-mais-procuradas.xlsx"),
        ("issuance", "Cotações e apólices emitidas", "cotacoes-e-apolices.xlsx"),
    ],
)
def test_report_excel_is_a_real_workbook(admin_client, slug, title, filename):
    response = admin_client.get(f"/api/v1/reports/{slug}/xlsx?from=2026-01-01&to=2026-12-31")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert filename in response["Content-Disposition"]
    assert response.content[:2] == b"PK"
    rows = _excel_rows(response)
    assert rows[0] == [title]
    assert ["Período", "01/01/2026 a 31/12/2026"] in rows
    assert ["Sem dados neste período."] in rows


def _report_quote(tenant, *, product_name, status="DRAFT"):
    product = Product.all_tenants.create(tenant_id=tenant.id, code=f"XL-{uuid.uuid4().hex[:8]}", name=product_name)
    plan = Plan.all_tenants.create(tenant_id=tenant.id, product_id=product.id, code=f"P-{uuid.uuid4().hex[:8]}", name="Plano")
    proposer = Proposer.all_tenants.create(
        tenant_id=tenant.id, proposer_type="INDIVIDUAL", display_name="Cliente", date_of_birth=datetime.date(1985, 1, 1),
        nif=f"{int(uuid.uuid4().hex[:8], 16) % 1_000_000_000:09d}LA042", registration_number=f"R-{uuid.uuid4().hex[:8]}",
    )
    Quote.all_tenants.create(tenant_id=tenant.id, proposer_id=proposer.id, plan_id=plan.id, status=status, created_by="test")


@pytest.mark.django_db
def test_report_excel_keeps_quantities_as_numbers(admin_client, tenant):
    _report_quote(tenant, product_name="Produto Excel", status="BOUND")
    rows = _excel_rows(admin_client.get("/api/v1/reports/top-products/xlsx"))
    assert ["Produto", "Cotações", "Emitidas"] in rows
    assert ["Produto Excel", 1, 1] in rows

    rows = _excel_rows(admin_client.get("/api/v1/reports/issuance/xlsx"))
    assert ["Cotação", "Emitida", 1] in rows


@pytest.mark.django_db
def test_report_excel_never_turns_a_name_into_a_formula(admin_client, tenant):
    import io

    import openpyxl

    _report_quote(tenant, product_name="=1+1")
    response = admin_client.get("/api/v1/reports/top-products/xlsx")
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    assert sheet["A8"].value == "=1+1" and sheet["A8"].data_type == "s"


@pytest.mark.django_db
def test_report_excel_rejects_an_unknown_report_and_needs_the_audit_scope(admin_client, tenant):
    assert admin_client.get("/api/v1/reports/desconhecido/xlsx").status_code == 404
    reader = make_client(tenant_id=tenant.id, roles=["UNDERWRITER"], scope="q360.read")
    assert reader.get("/api/v1/reports/top-products/xlsx").status_code == 403
