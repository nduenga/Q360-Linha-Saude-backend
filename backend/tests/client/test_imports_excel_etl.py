"""ROADMAP_ANGOLA_CUSTOMIZATION.md OD-004 (Product Owner decision,
2026-09-21): Excel (.xlsx) as the preferred bulk-import format, plus an
ETL pass that rejects null-lookalike placeholders and unknown
relationshipCode values at upload time (not only structural checks)."""
from __future__ import annotations

import io

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


def _csv_file(rows: list[str], name: str = "members.csv") -> SimpleUploadedFile:
    header = "relationshipCode,firstName,lastName,dateOfBirth,sexCode,externalReference"
    content = "\n".join([header, *rows]) + "\n"
    # Os dados escrevem-se em CSV, mas o ficheiro enviado é o modelo Excel (o único formato aceite).
    return SimpleUploadedFile(name.replace(".csv", ".xlsx"), csv_to_xlsx(content), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@pytest.mark.django_db
def test_upload_accepts_xlsx_and_creates_the_member(admin_client):
    proposer = _proposer(admin_client)
    file = _xlsx_file([["TITULAR", "Joao", "Silva", "1990-05-20", "M", "EXT-XLSX-1"]])

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
            ["TITULAR", "Joao", "Silva", "1990-05-20", "M", "EXT-1"],
            ["", "", "", "", "", ""],
            ["CONJUGE", "Maria", "Silva", "1992-01-01", "F", "EXT-2"],
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
            "TITULAR,Joao,Silva,1990-05-20,N/A,EXT-1",  # sexCode looks like a null placeholder
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
