"""Catálogo da plataforma no dia a dia: descarregar em Excel a versão em
vigor, ver as diferenças e o impacto antes de aprovar, a lista única de
pendentes, a vigência dos modelos, o assistente sem JSON e o teste de
fórmulas da plataforma."""
from __future__ import annotations

import datetime
import io

import pytest
from django.utils import timezone
from openpyxl import load_workbook

from tests.quote.test_formula_config_e2e import _priced_quote, approver  # noqa: F401  (fixture)
from tests.quote.test_platform_constants import TABLE, TABLES, _publish_formulas, _publish_table, checker, maker  # noqa: F401
from tests.quote.test_platform_parameters import REASON, _platform_key  # noqa: F401
from tests.quote.test_platform_templates import FORMULAS

TEMPLATES = "/api/v1/platform/templates"


@pytest.mark.django_db
def test_reference_table_excel_diff_impact_and_pending(maker, checker, admin_client, approver):  # noqa: F811
    _priced_quote(admin_client, approver)
    _publish_table(maker, checker)
    _publish_formulas(admin_client, approver, {"rules": [
        {"code": "fator_grupo", "name": "Fator", "order": 1,
         "expression": 'total_amount * tabela("fatores_teste", members_count, "fator")'},
    ]})

    exported = maker.get(f"{TABLES}/fatores_teste/xlsx")
    assert exported.status_code == 200
    sheet = load_workbook(io.BytesIO(b"".join(exported.streaming_content))).active
    assert [c.value for c in sheet[1]] == ["pessoas", "Fator"] and sheet.max_row == 3

    later = (timezone.now() + datetime.timedelta(days=5)).isoformat()
    new_rows = [{"pessoas": 1, "fator": "1.6"}, {"pessoas": 3, "fator": "1.3"}]
    proposed = maker.post(TABLES, {**TABLE, "rows": new_rows, "effectiveFrom": later}, format="json")
    assert proposed.status_code == 201, proposed.data
    diff = checker.get(f"{TABLES}/fatores_teste/versions/2/diff").data
    assert diff["summary"] == {"added": 1, "removed": 1, "changed": 1, "unchanged": 0}
    assert diff["changed"][0]["changes"][0] == {"column": "fator", "before": "1.5", "after": "1.6"}
    assert diff["impact"]["tenantCount"] == 1 and diff["impact"]["formulaCount"] == 1

    pending = checker.get("/api/v1/platform/pending-approvals").data
    table = next(p for p in pending if p["area"] == "REFERENCE_TABLE")
    assert "novas: 1" in table["summary"] and "1 seguradora(s) em 1 fórmula(s)" in table["impact"]
    assert table["createdByName"] == "maker"

    # aprovada com vigência futura: a versão 1 continua em vigor até lá
    checker.post(f"{TABLES}/fatores_teste/versions/2/approve", {}, format="json")
    assert maker.get(f"{TABLES}/fatores_teste").data["inEffect"]["versionNo"] == 1


@pytest.mark.django_db
def test_template_effective_date_excel_diff_and_wizard_catalog(maker, checker, admin_client):
    later = (timezone.now() + datetime.timedelta(days=2)).isoformat()
    body = {"code": "formulas-vigencia", "kind": "FORMULA_SET", "name": "Prémio mínimo",
            "content": {"configurations": {"pricing.formulas": FORMULAS}}, "reason": REASON, "effectiveFrom": later}
    assert maker.post(TEMPLATES, body, format="json").status_code == 201
    diff = checker.get(f"{TEMPLATES}/formulas-vigencia/versions/1/diff").data
    assert diff["summary"]["added"] == 1 and diff["baseVersionNo"] is None
    assert checker.post(f"{TEMPLATES}/formulas-vigencia/versions/1/approve", {}, format="json").status_code == 200
    # publicado, mas ainda fora de vigência: as seguradoras não o veem
    assert admin_client.get("/api/v1/templates").data == []
    assert admin_client.post("/api/v1/templates/formulas-vigencia/adopt", {}, format="json").status_code == 404

    exported = maker.get(f"{TEMPLATES}/formulas-vigencia/xlsx")
    rows = [[c.value for c in r] for r in load_workbook(io.BytesIO(b"".join(exported.streaming_content))).active.iter_rows()]
    assert ["pricing.formulas", "rules[0].expression", "max(total_amount, minimo * members_count)"] in rows
    # o Excel exportado volta a ser importado tal e qual
    from apps.business_config.application.platform_template_import import workbook_rows_to_content

    rebuilt = workbook_rows_to_content([str(v) for v in rows[0]], [[str(v) if v is not None else "" for v in r] for r in rows[1:]])
    assert rebuilt["configurations"]["pricing.formulas"]["rules"][0]["order"] == 1

    catalog = maker.get(f"{TEMPLATES}/catalog").data
    formula_kind = next(k for k in catalog["kinds"] if k["kind"] == "FORMULA_SET")
    assert [c["key"] for c in formula_kind["configurations"]] == ["pricing.formulas"]
    product = next(k for k in catalog["kinds"] if k["kind"] == "PRODUCT")
    plans = next(c for c in product["configurations"] if c["key"] == "product.plans")
    assert plans["formSchema"]["sections"][0]["repeatable"] is True
    assert {s["code"] for s in catalog["segments"]} == {"SAU", "SAG"}


@pytest.mark.django_db
def test_parameter_impact_and_platform_formula_test(maker):
    impact = maker.get("/api/v1/platform/system-parameters/tax.stamp_duty_pct/impact")
    assert impact.status_code == 200 and "seguradora" in impact.data["note"]

    tested = maker.post("/api/v1/platform/formula-engine/test",
                        {"expression": "max(total_amount, 1000) * 2", "variables": {"total_amount": 300}}, format="json")
    assert tested.status_code == 200, tested.data
    assert tested.data["result"] == "2000" and tested.data["variables"] == ["total_amount"]
    assert [s["operation"] for s in tested.data["steps"]][-1] == "*"
    broken = maker.post("/api/v1/platform/formula-engine/test", {"expression": "1 +"}, format="json")
    assert broken.status_code == 400 and broken.data["valid"] is False
