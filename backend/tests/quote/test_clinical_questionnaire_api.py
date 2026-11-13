from __future__ import annotations

import datetime

from tests.quote.test_quote_simulator import _scope


def _answer(question):
    kind = question["type"]
    if kind == "YES_NO":
        return False
    if kind == "NUMBER":
        return 170
    if kind == "DATE":
        return datetime.date.today().isoformat()
    if kind == "SELECT":
        return question["options"][0]
    if kind == "MULTI_SELECT":
        return [question["options"][0]]
    return "Resposta de teste"


def test_staff_questionnaire_endpoints_list_read_save_and_version_answers(admin_client):
    scope = _scope(admin_client, members=1)
    member_id = scope["memberIds"][0]
    base = f"/api/v1/quotes/{scope['quoteId']}"

    listed = admin_client.get(f"{base}/questionnaires")
    assert listed.status_code == 200, listed.data
    summary = listed.data["items"][0]
    assert summary["memberId"] == member_id
    assert summary["status"] == "NOT_STARTED"
    assert "answers" not in summary

    detail = admin_client.get(f"{base}/members/{member_id}/questionnaire")
    assert detail.status_code == 200, detail.data
    assert detail.data["answers"] == {}
    section = detail.data["schema"]["sections"][0]
    question = section["questions"][0]
    payload = {
        "answers": {question["key"]: _answer(question)},
        "currentSection": section["key"],
    }

    first_save = admin_client.put(f"{base}/members/{member_id}/questionnaire", payload, format="json")
    assert first_save.status_code == 200, first_save.data
    assert first_save.data["status"] == "IN_PROGRESS"
    assert first_save.data["rowVersion"] == 0

    update = admin_client.put(
        f"{base}/members/{member_id}/questionnaire",
        {**payload, "rowVersion": first_save.data["rowVersion"]},
        format="json",
    )
    assert update.status_code == 200, update.data
    assert update.data["rowVersion"] == 1

    stale = admin_client.put(
        f"{base}/members/{member_id}/questionnaire",
        {**payload, "rowVersion": first_save.data["rowVersion"]},
        format="json",
    )
    assert stale.status_code == 409, stale.data


def test_questionnaire_save_rejects_unknown_answer_keys(admin_client):
    scope = _scope(admin_client, members=1)
    member_id = scope["memberIds"][0]
    response = admin_client.put(
        f"/api/v1/quotes/{scope['quoteId']}/members/{member_id}/questionnaire",
        {"answers": {"notAQuestion": "value"}},
        format="json",
    )

    assert response.status_code == 400
    assert "não existe" in response.data["detail"]
