"""Q360-S3-04 acceptance criteria: "Template validado • Linhas inválidas
reportadas • Rollback possível". See
OPEN_DECISIONS.md#S03-IMPORT-001 for the (undocumented-elsewhere) CSV
column mapping and file-storage design this implementation uses."""
from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile


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


def _csv_file(rows: list[str], name: str = "members.csv") -> SimpleUploadedFile:
    header = "relationshipCode,firstName,lastName,dateOfBirth,sexCode,externalReference"
    content = "\n".join([header, *rows]) + "\n"
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")


@pytest.mark.django_db
def test_upload_validates_rows_and_reports_counts(admin_client):
    proposer = _proposer(admin_client)
    file = _csv_file(
        [
            "TITULAR,Joao,Silva,1990-05-20,M,EXT-1",
            ",Sem,Relacao,1990-05-20,M,EXT-2",  # invalid: missing relationshipCode
        ]
    )
    response = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    )
    assert response.status_code == 202
    body = response.data
    assert body["status"] == "VALIDATED"
    assert body["totalRows"] == 2
    assert body["validRows"] == 1
    assert body["invalidRows"] == 1


@pytest.mark.django_db
def test_commit_creates_only_valid_members(admin_client):
    proposer = _proposer(admin_client)
    file = _csv_file(
        [
            "TITULAR,Joao,Silva,1990-05-20,M,EXT-1",
            ",Sem,Relacao,1990-05-20,M,EXT-2",
        ]
    )
    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data

    commit = admin_client.post(
        f"/api/v1/member-imports/{uploaded['id']}/commit", {"confirm": True}, format="json"
    )
    assert commit.status_code == 202
    assert commit.data["status"] == "COMPLETED"

    members = admin_client.get(f"/api/v1/members?proposerId={proposer['id']}")
    assert len(members.data["items"]) == 1
    assert members.data["items"][0]["firstName"] == "Joao"


@pytest.mark.django_db
def test_commit_twice_is_conflict(admin_client):
    proposer = _proposer(admin_client)
    file = _csv_file(["TITULAR,Joao,Silva,1990-05-20,M,EXT-1"])
    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data
    admin_client.post(f"/api/v1/member-imports/{uploaded['id']}/commit", {"confirm": True}, format="json")

    second = admin_client.post(
        f"/api/v1/member-imports/{uploaded['id']}/commit", {"confirm": True}, format="json"
    )
    assert second.status_code == 409
    assert second.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_commit_without_proposer_is_conflict(admin_client):
    file = _csv_file(["TITULAR,Joao,Silva,1990-05-20,M,EXT-1"])
    uploaded = admin_client.post("/api/v1/member-imports", {"file": file}, format="multipart").data
    assert uploaded["proposerId"] is None

    response = admin_client.post(
        f"/api/v1/member-imports/{uploaded['id']}/commit", {"confirm": True}, format="json"
    )
    assert response.status_code == 409
    assert response.data["code"] == "CONFLICT"


@pytest.mark.django_db
def test_get_import_job_status(admin_client):
    proposer = _proposer(admin_client)
    file = _csv_file(["TITULAR,Joao,Silva,1990-05-20,M,EXT-1"])
    uploaded = admin_client.post(
        "/api/v1/member-imports", {"proposerId": proposer["id"], "file": file}, format="multipart"
    ).data

    response = admin_client.get(f"/api/v1/member-imports/{uploaded['id']}")
    assert response.status_code == 200
    assert response.data["id"] == uploaded["id"]
