"""ROADMAP_ANGOLA_CUSTOMIZATION.md OD-004 (Product Owner decision,
2026-09-21): Excel (.xlsx) as the preferred bulk-import format, plus an
ETL pass that rejects null-lookalike placeholders and unknown
relationshipCode values at upload time (not only structural checks)."""
from __future__ import annotations

import io
from pathlib import Path

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from tests.xlsx import csv_to_xlsx


def _proposer(client) -> dict:
    return client.post(
        "/api/v1/proposers",
        {
            "proposerType": "ORGANISATION",
            "displayName": "Group Co",
            "registrationNumber": "5417000000",
            "email": "group@example.com",
            "phone": "+244900000000",
        },
    ).data


def _xlsx_file(rows: list[list[str]], name: str = "members.xlsx") -> SimpleUploadedFile:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["relationshipCode", "firstName", "lastName", "dateOfBirth", "sexCode", "externalReference"])
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return SimpleUploadedFile(
        name,
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _organisation_household_xlsx(rows: list[list[str]]) -> SimpleUploadedFile:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append([
        "Tipo de pessoa", "Referência do colaborador titular", "Relação com o titular",
        "Nome", "Apelido", "Data de nascimento", "Sexo", "Referência externa", "E-mail", "Telefone",
    ])
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return SimpleUploadedFile(
        "colaboradores-e-familias.xlsx",
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _csv_file(rows: list[str], name: str = "members.csv") -> SimpleUploadedFile:
    header = "relationshipCode,firstName,lastName,dateOfBirth,sexCode,externalReference"
    content = "\n".join([header, *rows]) + "\n"
    # Os dados escrevem-se em CSV, mas o ficheiro enviado é o modelo Excel (o único formato aceite).
    return SimpleUploadedFile(name.replace(".csv", ".xlsx"), csv_to_xlsx(content), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@pytest.mark.django_db
def test_upload_accepts_xlsx_and_creates_the_member(admin_client):
    proposer = _proposer(admin_client)
    file = _xlsx_file([["COLABORADOR", "Joao", "Silva", "1990-05-20", "M", "EXT-XLSX-1"]])

    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data
    assert uploaded["status"] == "VALIDATED"
    assert uploaded["totalRows"] == 1
    assert uploaded["validRows"] == 1

    commit = admin_client.post(
        f"/api/v1/member-imports/{uploaded['id']}/commit", {"confirm": True}, format="json"
    )
    assert commit.status_code == 202
    members = admin_client.get(f"/api/v1/members?proposerId={proposer['id']}")
    assert members.data["items"][0]["firstName"] == "Joao"


@pytest.mark.django_db
def test_xlsx_blank_rows_are_skipped_not_counted_as_errors(admin_client):
    proposer = _proposer(admin_client)
    file = _xlsx_file(
        [
            ["COLABORADOR", "Joao", "Silva", "1990-05-20", "M", "EXT-1"],
            ["", "", "", "", "", ""],
            ["COLABORADOR", "Maria", "Silva", "1992-01-01", "F", "EXT-2"],
        ]
    )
    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data
    assert uploaded["totalRows"] == 2
    assert uploaded["validRows"] == 2


@pytest.mark.django_db
def test_null_lookalike_placeholder_is_rejected_as_invalid_row(admin_client):
    proposer = _proposer(admin_client)
    file = _csv_file(
        [
            "COLABORADOR,Joao,Silva,1990-05-20,N/A,EXT-1",  # sexCode looks like a null placeholder
        ]
    )
    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data
    assert uploaded["totalRows"] == 1
    assert uploaded["validRows"] == 0
    assert uploaded["invalidRows"] == 1


@pytest.mark.django_db
def test_unknown_relationship_code_is_rejected_at_upload_not_only_commit(admin_client):
    proposer = _proposer(admin_client)
    file = _csv_file(["SOBRINHO,Joao,Silva,1990-05-20,M,EXT-1"])
    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data
    assert uploaded["validRows"] == 0
    assert uploaded["invalidRows"] == 1


@pytest.mark.django_db
def test_organisation_import_creates_optional_households_for_linked_dependants(admin_client):
    proposer = _proposer(admin_client)
    file = _organisation_household_xlsx([
        ["COLABORADOR", "", "COLABORADOR", "Ana", "Silva", "1985-05-21", "F", "FUNC-001"],
        ["DEPENDENTE", "FUNC-001", "CONJUGE", "Paulo", "Silva", "1983-11-02", "M", "FAM-001"],
        ["DEPENDENTE", "FUNC-001", "FILHO", "Marta", "Silva", "2012-03-14", "F", "FAM-002"],
        ["COLABORADOR", "", "COLABORADOR", "Rui", "Costa", "1991-08-30", "M", "FUNC-002"],
    ])

    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data
    assert (uploaded["totalRows"], uploaded["validRows"], uploaded["invalidRows"]) == (4, 4, 0)

    committed = admin_client.post(
        f"/api/v1/member-imports/{uploaded['id']}/commit", {"confirm": True}, format="json"
    )
    assert committed.status_code == 202
    all_members = admin_client.get(f"/api/v1/members?proposerId={proposer['id']}")
    assert len(all_members.data["items"]) == 4
    directory_members = admin_client.get(
        f"/api/v1/members?proposerId={proposer['id']}&excludeHouseholdDependents=true"
    )
    assert len(directory_members.data["items"]) == 2
    assert all(member["relationshipCode"] == "COLABORADOR" for member in directory_members.data["items"])

    households = admin_client.get(f"/api/v1/households?proposerId={proposer['id']}")
    assert households.status_code == 200
    assert len(households.data) == 1
    memberships = admin_client.get(f"/api/v1/households/{households.data[0]['id']}/members")
    assert len(memberships.data) == 3
    assert sum(1 for item in memberships.data if item["member"]["relationshipCode"] == "COLABORADOR") == 1
    assert sum(1 for item in memberships.data if item["member"]["relationshipCode"] in {"CONJUGE", "FILHO"}) == 2


@pytest.mark.django_db
def test_organisation_import_creates_one_titular_with_contact_details(admin_client):
    proposer = _proposer(admin_client)
    file = _organisation_household_xlsx([
        ["TITULAR", "", "TITULAR", "Rosa", "Exemplo", "1979-02-11", "F", "", "rosa@empresa-teste.ao", "+244900000001"],
        ["COLABORADOR", "", "COLABORADOR", "Ana", "Silva", "1985-05-21", "F", "FUNC-001", "", ""],
    ])

    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data
    assert (uploaded["totalRows"], uploaded["validRows"], uploaded["invalidRows"]) == (2, 2, 0)

    committed = admin_client.post(
        f"/api/v1/member-imports/{uploaded['id']}/commit", {"confirm": True}, format="json"
    )
    assert committed.status_code == 202
    members = admin_client.get(f"/api/v1/members?proposerId={proposer['id']}").data["items"]
    titular = next(member for member in members if member["relationshipCode"] == "TITULAR")
    assert titular["firstName"] == "Rosa"
    assert titular["lastName"] == "Exemplo"
    assert titular["dateOfBirth"] == "1979-02-11"
    assert titular["sexCode"] == "F"
    assert titular["attributes"] == {
        "email": "rosa@empresa-teste.ao",
        "phone": "+244900000001",
    }
    directory_members = admin_client.get(
        f"/api/v1/members?proposerId={proposer['id']}&excludeHouseholdDependents=true"
    )
    assert len(directory_members.data["items"]) == 2
    assert {member["relationshipCode"] for member in directory_members.data["items"]} == {
        "TITULAR",
        "COLABORADOR",
    }
    assert admin_client.get(f"/api/v1/households?proposerId={proposer['id']}").data == []


@pytest.mark.django_db
def test_organisation_import_rejects_titular_email_matching_organisation_email(admin_client):
    proposer = _proposer(admin_client)
    file = _organisation_household_xlsx([
        ["TITULAR", "", "TITULAR", "Rosa", "Exemplo", "1979-02-11", "F", "", proposer["email"], "+244900000001"],
    ])

    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data
    assert uploaded["validRows"] == 0
    assert uploaded["invalidRows"] == 1


@pytest.mark.django_db(transaction=True)
def test_organisation_import_invites_titular_without_replacing_organisation_email(
    admin_client, tenant,
):
    from django.core import mail

    from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer

    proposer = _proposer(admin_client)
    organisation_email = proposer["email"]
    titular_email = "rosa.titular@empresa-teste.ao"
    mail.outbox.clear()
    file = _organisation_household_xlsx([
        ["TITULAR", "", "TITULAR", "Rosa", "Exemplo", "1979-02-11", "F", "", titular_email, "+244900000001"],
    ])
    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data
    assert uploaded["validRows"] == 1

    committed = admin_client.post(
        f"/api/v1/member-imports/{uploaded['id']}/commit", {"confirm": True}, format="json"
    )
    assert committed.status_code == 202
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [titular_email]
    assert "rosa.titular%40empresa-teste.ao" in mail.outbox[0].body

    account = CustomerAccount.all_tenants.get(tenant_id=tenant.id, email=titular_email)
    assert CustomerAccountProposer.all_tenants.filter(
        customer_account=account, proposer_id=proposer["id"]
    ).exists()
    proposer_detail = admin_client.get(f"/api/v1/proposers/{proposer['id']}")
    assert proposer_detail.data["email"] == organisation_email


@pytest.mark.django_db
def test_organisation_import_rejects_a_second_titular_in_the_same_file(admin_client):
    proposer = _proposer(admin_client)
    file = _organisation_household_xlsx([
        ["TITULAR", "", "TITULAR", "Rosa", "Exemplo", "1979-02-11", "F", "", "rosa@empresa-teste.ao", "+244900000001"],
        ["TITULAR", "", "TITULAR", "Paulo", "Exemplo", "1978-04-03", "M", "", "paulo@empresa-teste.ao", "+244900000002"],
    ])

    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data
    assert (uploaded["totalRows"], uploaded["validRows"], uploaded["invalidRows"]) == (2, 1, 1)


@pytest.mark.django_db
def test_organisation_member_family_test_workbook_imports_thirty_people(admin_client):
    proposer = _proposer(admin_client)
    path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "modelos_importacao"
        / "12_Exemplo_Colaboradores_e_Familiares_TESTE.xlsx"
    )
    uploaded_file = SimpleUploadedFile(
        path.name,
        path.read_bytes(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    uploaded_response = admin_client.post(
        "/api/v1/member-imports",
        {"proposerId": proposer["id"], "file": uploaded_file},
        format="multipart",
    )

    assert uploaded_response.status_code == 202, uploaded_response.data
    assert (
        uploaded_response.data["totalRows"],
        uploaded_response.data["validRows"],
        uploaded_response.data["invalidRows"],
    ) == (30, 30, 0)
    committed = admin_client.post(
        f"/api/v1/member-imports/{uploaded_response.data['id']}/commit",
        {"confirm": True},
        format="json",
    )
    assert committed.status_code == 202, committed.data

    households = admin_client.get(f"/api/v1/households?proposerId={proposer['id']}")
    assert households.status_code == 200
    assert len(households.data) == 8
    memberships = [
        item
        for household in households.data
        for item in admin_client.get(f"/api/v1/households/{household['id']}/members").data
    ]
    assert sum(item["member"]["relationshipCode"] == "COLABORADOR" for item in memberships) == 8
    assert sum(item["member"]["relationshipCode"] in {"CONJUGE", "FILHO"} for item in memberships) == 19
