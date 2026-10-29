"""Os modelos Excel descarregados trazem vários dados de teste: cada um tem
de ser importado tal como vem, sem nenhuma linha recusada."""
from __future__ import annotations

from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.business_config.application import platform_template_import, platform_templates
from apps.foundation.application import platform_reference_service
from apps.foundation.interfaces.import_template_views import TEMPLATES

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _organisation(client) -> str:
    return client.post(
        "/api/v1/proposers",
        {
            "proposerType": "ORGANISATION",
            "displayName": "Empresa Exemplo",
            "registrationNumber": "5417000001",
            "email": "rh@empresa-exemplo.ao",
            "phone": "+244900000001",
        },
    ).data["id"]


def _download(client, url: str, name: str) -> SimpleUploadedFile:
    response = client.get(url)
    assert response.status_code == 200
    return SimpleUploadedFile(name, b"".join(response.streaming_content) if response.streaming else response.content,
                              content_type=XLSX)


@pytest.mark.django_db
def test_members_template_imports_every_example_row(admin_client):
    proposer_id = _organisation(admin_client)
    file = _download(admin_client, "/api/v1/import-templates/MEMBERS", "modelo-membros.xlsx")
    uploaded = admin_client.post("/api/v1/member-imports", {"proposerId": proposer_id, "file": file}, format="multipart").data
    rows = len(TEMPLATES["MEMBERS"]["examples"])
    assert rows >= 10
    assert (uploaded["totalRows"], uploaded["validRows"], uploaded["invalidRows"]) == (rows, rows, 0)
    commit = admin_client.post(f"/api/v1/member-imports/{uploaded['id']}/commit", {"confirm": True}, format="json")
    assert commit.data["status"] == "COMPLETED"
    assert len(admin_client.get(f"/api/v1/members?proposerId={proposer_id}&pageSize=100").data["items"]) == rows


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["CLAIMS", "PREMIUMS"])
def test_claims_and_premiums_templates_import_every_example_row(admin_client, kind):
    proposer_id = _organisation(admin_client)
    file = _download(admin_client, f"/api/v1/claims/import-template?kind={kind}", f"modelo-{kind.lower()}.xlsx")
    response = admin_client.post("/api/v1/claims/imports", {"file": file, "kind": kind, "proposerId": proposer_id},
                                 format="multipart")
    assert response.status_code == 201, response.data
    assert response.data["errors"] == []
    assert response.data["importedRows"] == len(TEMPLATES[kind]["examples"]) > 1


@pytest.mark.django_db
def test_benefits_template_creates_every_example_coverage(admin_client):
    file = _download(admin_client, "/api/v1/import-templates/BENEFITS", "modelo-coberturas.xlsx")
    response = admin_client.post("/api/v1/benefits/import", {"file": file, "dryRun": "true"}, format="multipart")
    assert response.status_code == 200
    assert response.data["errors"] == []
    assert response.data["created"] == [row[0] for row in TEMPLATES["BENEFITS"]["examples"]]


def test_reference_table_template_has_a_valid_row_per_province():
    parsed = platform_reference_service.parse_workbook_preview(platform_reference_service.build_import_template())
    assert parsed["headers"] == ["codigo", "nome", "fator"]
    assert len(parsed["rows"]) == 18
    platform_reference_service.validate_table(
        code="provincias", name="Províncias", key_column="codigo",
        columns=[{"code": "codigo"}, {"code": "nome"}, {"code": "fator", "type": "NUMBER"}],
        rows=[dict(zip(parsed["headers"], row)) for row in parsed["rows"]],
    )


def test_supplier_template_passes_the_real_validation():
    content = platform_template_import.parse_template_workbook(platform_template_import.build_import_template())["content"]
    assert [plan["code"] for plan in content["configurations"]["product.plans"]["plans"]] == ["basico", "standard", "premium"]
    platform_templates.validate_content("PRODUCT", content)


# --- Pacote estático docs/modelos_importacao: os exemplos TESTE também têm de entrar inteiros.
PACKAGE = Path(__file__).resolve().parents[3] / "docs" / "modelos_importacao"


def _package_file(name: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, (PACKAGE / name).read_bytes(), content_type=XLSX)


@pytest.mark.django_db
def test_package_member_claims_and_premium_examples_import_without_errors(admin_client):
    proposer_id = _organisation(admin_client)
    uploaded = admin_client.post("/api/v1/member-imports",
                                 {"proposerId": proposer_id, "file": _package_file("02_Exemplo_Membros_TESTE.xlsx")},
                                 format="multipart").data
    assert uploaded["invalidRows"] == 0 and uploaded["validRows"] >= 30
    assert admin_client.post(f"/api/v1/member-imports/{uploaded['id']}/commit", {"confirm": True},
                             format="json").data["status"] == "COMPLETED"
    for kind, name in (("CLAIMS", "04_Exemplo_Historico_Sinistros_36_Meses_TESTE.xlsx"),
                       ("PREMIUMS", "06_Exemplo_Historico_Premios_36_Meses_TESTE.xlsx")):
        response = admin_client.post("/api/v1/claims/imports",
                                     {"file": _package_file(name), "kind": kind, "proposerId": proposer_id},
                                     format="multipart")
        assert response.status_code == 201, response.data
        assert response.data["errors"] == []


@pytest.mark.django_db
def test_package_benefit_and_reference_examples_are_valid(admin_client):
    response = admin_client.post("/api/v1/benefits/import",
                                 {"file": _package_file("08_Exemplo_Coberturas_TESTE.xlsx"), "dryRun": "true"},
                                 format="multipart")
    assert response.data["errors"] == [] and len(response.data["created"]) == 10
    parsed = platform_reference_service.parse_workbook_preview((PACKAGE / "10_Exemplo_Tabela_Referencia_TESTE.xlsx").read_bytes())
    assert len(parsed["rows"]) == 18
    platform_reference_service.validate_table(
        code="provincias", name="Províncias", key_column="provincia",
        columns=[{"code": "provincia"}, {"code": "fator", "type": "NUMBER"}],
        rows=[dict(zip(["provincia", "fator"], row)) for row in parsed["rows"]],
    )
