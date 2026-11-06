"""Garantias do backend para a nova interface (Manual visual v2), pela API real."""
from __future__ import annotations

import io
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer, PortalRequest
from apps.policy.infrastructure.models import PremiumInstallment
from apps.quote.infrastructure.models import ClinicalQuestionnaire, Quote
from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole
from tests.policy.conftest import make_client
from tests.policy.test_emission import _BODY, _PAYMENT
from tests.policy.test_issuance import _approved_quote, _approver, _eligibility_rule, _nif_for_suffix, _parameter_set, _plan, _rating_table

SCOPE = "q360.read q360.write q360.approve"


def _emit(tenant, quote, *, payment=None, frequency="ANUAL"):
    body = {**_BODY, "rowVersion": quote["rowVersion"], "paymentFrequency": frequency}
    if payment:
        body["payment"] = payment
    response = _approver(tenant).post(f"/api/v1/quotes/{quote['id']}/policy/emit", body, format="json")
    assert response.status_code == 201, response.data
    return response.data


def _another_approved(client, tenant, *, plan_id, suffix, stop_at_submit=False):
    """Outra cotação aprovada no mesmo plano: a configuração publicada é única por seguradora."""
    proposer = client.post("/api/v1/proposers", {
        "proposerType": "INDIVIDUAL", "dateOfBirth": "1985-04-12", "displayName": f"Outro {suffix}",
        "registrationNumber": _nif_for_suffix(suffix), "email": f"outro{suffix}@demo.q360.local".lower(), "phone": "+244900000002",
    }).data
    member = client.post("/api/v1/members", {
        "firstName": "Outra", "proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01",
    }).data
    quote = client.post("/api/v1/quotes", {"planId": plan_id, "proposerId": proposer["id"]}, format="json").data
    client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member["id"]}, format="json")
    client.post(f"/api/v1/quotes/{quote['id']}/price")
    ready = client.get(f"/api/v1/quotes/{quote['id']}").data
    submitted = client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": ready["rowVersion"]}, format="json").data
    if stop_at_submit:
        return submitted
    approved = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]}, format="json",
    ).data
    return {**approved, "memberId": member["id"], "proposerId": proposer["id"]}


def _ready_quote(client, *, suffix):
    plan_ref = _plan(client, product_code=f"V2-{suffix}")
    _parameter_set(client, code=f"V2-PARAMS-{suffix}")
    _rating_table(client, code=f"V2-TABLE-{suffix}")
    _eligibility_rule(client, code=f"V2-ELIG-{suffix}", config={})
    proposer = client.post("/api/v1/proposers", {
        "proposerType": "INDIVIDUAL", "dateOfBirth": "1985-04-12", "displayName": f"Ana Teste {suffix}",
        "registrationNumber": _nif_for_suffix(suffix), "email": f"ana{suffix}@demo.q360.local".lower(), "phone": "+244 923 456 789",
    }).data
    member = client.post("/api/v1/members", {
        "firstName": "Ana", "lastName": "Teste", "proposerId": proposer["id"], "relationshipCode": "TITULAR", "dateOfBirth": "1990-01-01",
    }).data
    quote = client.post("/api/v1/quotes", {**plan_ref, "proposerId": proposer["id"]}, format="json").data
    return quote, proposer, member


def _priced(client, *, suffix):
    quote, proposer, member = _ready_quote(client, suffix=suffix)
    client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member["id"]}, format="json")
    client.post(f"/api/v1/quotes/{quote['id']}/price")
    return client.get(f"/api/v1/quotes/{quote['id']}").data, proposer, member


def _submitted(client, *, suffix):
    quote, proposer, member = _priced(client, suffix=suffix)
    response = client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json")
    assert response.status_code == 200, response.data
    return response.data, proposer, member


def _task(client, quote_id):
    return client.get(f"/api/v1/quotes/{quote_id}/review").data


def _staff(tenant, name, role="SUBSCRIBER"):
    account = StaffAccount.all_tenants.create(tenant_id=tenant.id, email=f"{uuid.uuid4().hex}@demo.q360.local", name=name, password_hash="x")
    StaffAccountRole.all_tenants.create(tenant_id=tenant.id, staff_account=account, role=role)
    return account


# ---------------------------------------------------------- 1.ª prestação
@pytest.mark.django_db
def test_the_same_payment_reference_cannot_be_registered_twice(admin_client, tenant):
    first = _approved_quote(admin_client, tenant, suffix="D1")
    _emit(tenant, first, payment={**_PAYMENT, "paymentReference": "RF 0041-2026"})

    second = _another_approved(admin_client, tenant, plan_id=first["planId"], suffix="D2")
    policy = _emit(tenant, second)
    response = _approver(tenant).post(
        f"/api/v1/policies/{policy['id']}/installments/1/payment",
        {"paidAt": "2026-06-10T15:00:00Z", "paymentReference": "rf  0041-2026", "rowVersion": policy["rowVersion"]},
        format="json",
    )
    assert response.status_code == 409
    assert response.data["code"] == "PAYMENT-REFERENCE-DUPLICATE"
    assert admin_client.get(f"/api/v1/policies/{policy['id']}").data["status"] == "PENDING_FIRST_PREMIUM"

    retried = _approver(tenant).post(
        f"/api/v1/policies/{policy['id']}/installments/1/payment",
        {"paidAt": "2026-06-10T15:00:00Z", "paymentReference": "RF 0042-2026", "rowVersion": policy["rowVersion"]},
        format="json",
    )
    assert retried.status_code == 200, retried.data
    assert retried.data["status"] == "ACTIVE"


@pytest.mark.django_db
def test_collections_list_explains_the_first_premium_action(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="D3")
    policy = _emit(tenant, quote)
    rows = admin_client.get("/api/v1/installments", {"kind": "FIRST_PREMIUM"}).data["items"]
    row = next(r for r in rows if r["policyId"] == policy["id"])
    assert row["canRegisterPayment"] is True
    assert "passa a Ativa" in row["paymentEffect"]
    assert row["statusLabel"] == "A aguardar"
    assert row["policyStatusLabel"] == "Pendente"


# ------------------------------------------------------------ questionário
@pytest.mark.django_db
def test_questionnaire_keeps_progress_and_clears_the_requirement(admin_client, tenant):
    from apps.product.infrastructure.models import Plan

    quote, _, member = _priced(admin_client, suffix="Q1")
    Plan.all_tenants.filter(id=quote["planId"]).update(settings_json={"segment": "INDIVIDUAL_FAMILY"})
    url = f"/api/v1/quotes/{quote['id']}/members/{member['id']}/questionnaire"

    pending = admin_client.get(f"/api/v1/quotes/{quote['id']}/requirements").data
    warning = next(w for w in pending["warnings"] if w["code"] == "CLINICAL_QUESTIONNAIRE_REQUIRED")
    assert warning["action"] == "FILL_QUESTIONNAIRE" and warning["questionnaireStatus"] == "NOT_STARTED"
    assert admin_client.get(url).data["status"] == "NOT_STARTED"
    saved = admin_client.put(url, {"answers": {"heightCm": 170, "smoker": False}, "currentSection": "habits"}, format="json")
    assert saved.status_code == 200, saved.data
    assert saved.data["status"] == "IN_PROGRESS" and saved.data["progress"]["answered"] == 2

    blocked = admin_client.post(f"{url}/complete", {"rowVersion": saved.data["rowVersion"]}, format="json")
    assert blocked.status_code == 409

    saved = admin_client.put(url, {
        "answers": {"weightKg": 70, "regularAlcohol": False, "chronicCondition": True, "hospitalised": False, "regularMedication": False},
        "rowVersion": saved.data["rowVersion"],
    }, format="json")
    assert saved.data["progress"] == {"answered": 7, "required": 9}, "a resposta Sim abre as perguntas seguintes"
    saved = admin_client.put(url, {
        "answers": {"chronicConditionName": "Hipertensão", "chronicConditionTreated": True},
        "rowVersion": saved.data["rowVersion"],
    }, format="json")
    done = admin_client.post(f"{url}/complete", {"rowVersion": saved.data["rowVersion"]}, format="json")
    assert done.status_code == 200, done.data
    assert done.data["status"] == "COMPLETED" and done.data["hasDeclarations"] is True

    report = admin_client.get(f"/api/v1/quotes/{quote['id']}/requirements").data
    assert not [w for w in report["warnings"] if w["code"] == "CLINICAL_QUESTIONNAIRE_REQUIRED"]
    assert [i for i in report["info"] if i["code"] == "CLINICAL_QUESTIONNAIRE_COMPLETED"]


@pytest.mark.django_db
def test_questionnaire_answers_stay_out_of_reach_of_other_profiles(admin_client, tenant):
    quote, _, member = _priced(admin_client, suffix="Q2")
    url = f"/api/v1/quotes/{quote['id']}/members/{member['id']}/questionnaire"
    director = make_client(tenant_id=tenant.id, roles=["TECHNICAL_DIRECTOR"], scope="q360.read q360.approve", actor_id="dir-1")
    assert director.get(url).status_code == 403
    assert admin_client.put(url, {"answers": {"heightCm": "alto"}}, format="json").status_code == 400
    assert admin_client.put(url, {"answers": {"inventada": True}}, format="json").status_code == 400


@pytest.mark.django_db
def test_customer_only_reaches_the_questionnaire_that_was_requested(admin_client, tenant):
    quote, proposer, member = _priced(admin_client, suffix="Q3")
    url = f"/api/v1/quotes/{quote['id']}/members/{member['id']}/questionnaire"
    account, _ = CustomerAccount.all_tenants.get_or_create(tenant_id=tenant.id, email=proposer["email"])
    CustomerAccountProposer.all_tenants.get_or_create(tenant_id=tenant.id, customer_account=account, proposer_id=proposer["id"])

    response = admin_client.post(f"{url}/customer-request")
    assert response.status_code == 200, response.data
    assert ClinicalQuestionnaire.all_tenants.get(quote_id=quote["id"]).requested_from_customer_at is not None


# ------------------------------------------------------------- atribuição
@pytest.mark.django_db
def test_reviews_are_assigned_and_filtered(admin_client, tenant):
    submitted, _, _ = _submitted(admin_client, suffix="R1")
    reviewer = _approver(tenant)
    task = _task(admin_client, submitted["id"])
    assert task["assignedTo"] is None and task["status"] == "OPEN"
    assert task["canDecide"] is False

    assert admin_client.post(f"/api/v1/reviews/{task['id']}/assignment", {}, format="json").status_code == 403

    assigned = reviewer.post(f"/api/v1/reviews/{task['id']}/assignment", {}, format="json")
    assert assigned.status_code == 200, assigned.data
    assert assigned.data["assignedTo"] == "approver-1" and assigned.data["status"] == "IN_PROGRESS"

    mine = reviewer.get("/api/v1/reviews", {"assignment": "mine"}).data["items"]
    assert [row["id"] for row in mine] == [task["id"]]
    assert reviewer.get("/api/v1/reviews", {"assignment": "unassigned"}).data["items"] == []


@pytest.mark.django_db
def test_batch_assignment_reports_each_task(admin_client, tenant):
    first, _, _ = _submitted(admin_client, suffix="R2")
    task = _task(admin_client, first["id"])
    missing = uuid.uuid4()
    response = _approver(tenant).post(
        "/api/v1/reviews/assignments", {"taskIds": [task["id"], str(missing)]}, format="json"
    )
    assert response.status_code == 200, response.data
    assert [row["id"] for row in response.data["assigned"]] == [task["id"]]
    assert response.data["failed"][0]["taskId"] == str(missing)


@pytest.mark.django_db
def test_alert_when_no_other_reviewer_exists(admin_client, tenant):
    submitted, _, _ = _submitted(admin_client, suffix="R3")
    task = _task(admin_client, submitted["id"])
    report = _approver(tenant).get(f"/api/v1/reviews/{task['id']}/eligible-reviewers").data
    assert report["noEligibleReviewer"] is True and report["alert"]

    colleague = _staff(tenant, "Rui Lemos")
    report = _approver(tenant).get(f"/api/v1/reviews/{task['id']}/eligible-reviewers").data
    assert report["eligibleReviewers"] == [{"id": str(colleague.id), "name": "Rui Lemos"}]
    assigned = _approver(tenant).post(
        f"/api/v1/reviews/{task['id']}/assignment", {"assigneeId": str(colleague.id)}, format="json"
    )
    assert assigned.data["assignedToName"] == "Rui Lemos"


@pytest.mark.django_db
def test_the_creator_can_decide_when_someone_else_submitted(admin_client, tenant):
    from apps.foundation.infrastructure.models import AuditEvent

    quote, _, _ = _priced(admin_client, suffix="R4")
    other = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="actor-2")
    submitted = other.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": quote["rowVersion"]}, format="json").data
    decision = {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]}
    assert other.post(f"/api/v1/quotes/{quote['id']}/decision", decision, format="json").status_code == 403
    response = admin_client.post(f"/api/v1/quotes/{quote['id']}/decision", decision, format="json")
    assert response.status_code == 200, response.data
    event = AuditEvent.all_tenants.filter(tenant_id=tenant.id, action="quote.decision.approve").latest("occurred_at")
    assert event.metadata_json["decidedByCreator"] is True


@pytest.mark.django_db
def test_the_same_person_creating_and_submitting_never_decides(admin_client, tenant):
    submitted, _, _ = _submitted(admin_client, suffix="R6")
    response = admin_client.post(
        f"/api/v1/quotes/{submitted['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]}, format="json",
    )
    assert response.status_code == 403


# ------------------------------------------------------------ anular envio
@pytest.mark.django_db
def test_submission_can_be_undone_while_nobody_took_it(admin_client, tenant):
    submitted, _, _ = _submitted(admin_client, suffix="U1")
    assert submitted["undoUntil"] is not None
    undone = admin_client.post(f"/api/v1/quotes/{submitted['id']}/submit/undo", {"rowVersion": submitted["rowVersion"]}, format="json")
    assert undone.status_code == 200, undone.data
    assert undone.data["status"] == "READY" and undone.data["displayStatus"] == "READY"
    again = admin_client.post(f"/api/v1/quotes/{submitted['id']}/submit", {"rowVersion": undone.data["rowVersion"]}, format="json")
    assert again.status_code == 200, again.data


@pytest.mark.django_db
def test_submission_cannot_be_undone_after_assignment_or_by_others(admin_client, tenant):
    submitted, _, _ = _submitted(admin_client, suffix="U2")
    other = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="actor-2")
    url = f"/api/v1/quotes/{submitted['id']}/submit/undo"
    assert other.post(url, {"rowVersion": submitted["rowVersion"]}, format="json").status_code == 403
    task = _task(admin_client, submitted["id"])
    _approver(tenant).post(f"/api/v1/reviews/{task['id']}/assignment", {}, format="json")
    assert admin_client.post(url, {"rowVersion": submitted["rowVersion"]}, format="json").status_code == 409


@pytest.mark.django_db
def test_submission_cannot_be_undone_after_the_window(admin_client, tenant):
    import datetime

    submitted, _, _ = _submitted(admin_client, suffix="U3")
    Quote.all_tenants.filter(id=submitted["id"]).update(
        submitted_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    )
    response = admin_client.post(f"/api/v1/quotes/{submitted['id']}/submit/undo", {"rowVersion": submitted["rowVersion"]}, format="json")
    assert response.status_code == 409


# ------------------------------------------------------ cotação numa página
@pytest.mark.django_db
def test_workspace_saves_checks_eligibility_and_prices_in_one_call(admin_client, tenant):
    quote, _, member = _ready_quote(admin_client, suffix="W1")
    url = f"/api/v1/quotes/{quote['id']}/workspace"
    response = admin_client.put(url, {"memberIds": [member["id"]], "rowVersion": quote["rowVersion"]}, format="json")
    assert response.status_code == 200, response.data
    data = response.data
    assert data["status"] == "READY" and data["pricingError"] is None
    assert data["members"][0]["eligibilityDecision"] is not None
    assert data["premium"] is not None
    assert data["readiness"]["ready"] is True
    questionnaire = next(c for c in data["readiness"]["checks"] if c["code"] == "CLINICAL_QUESTIONNAIRE")
    assert questionnaire["blocking"] is False

    emptied = admin_client.put(url, {"memberIds": [], "rowVersion": data["rowVersion"]}, format="json")
    assert emptied.status_code == 200, emptied.data
    assert emptied.data["members"] == [] and emptied.data["readiness"]["ready"] is False


@pytest.mark.django_db
def test_workspace_refuses_a_stale_version(admin_client, tenant):
    quote, _, member = _ready_quote(admin_client, suffix="W2")
    url = f"/api/v1/quotes/{quote['id']}/workspace"
    response = admin_client.put(url, {"memberIds": [member["id"]], "rowVersion": quote["rowVersion"] + 7}, format="json")
    assert response.status_code == 409


# ------------------------------------------------------------ fila de trabalho
@pytest.mark.django_db
def test_work_queue_counts_match_the_lists(admin_client, tenant):
    first = _approved_quote(admin_client, tenant, suffix="F1")
    pending = _emit(tenant, first)
    approved = _another_approved(admin_client, tenant, plan_id=first["planId"], suffix="F2")
    submitted = _another_approved(admin_client, tenant, plan_id=first["planId"], suffix="F3", stop_at_submit=True)

    queue = _approver(tenant).get("/api/v1/work-queue")
    assert queue.status_code == 200, queue.data
    counts = {row["kind"]: row["count"] for row in queue.data["counts"]}
    open_reviews = _approver(tenant).get("/api/v1/reviews", {"status": "OPEN"}).data["items"]
    assert counts["REVIEW"] == len(open_reviews) == 1
    first_premiums = admin_client.get("/api/v1/installments", {"kind": "FIRST_PREMIUM"}).data["items"]
    assert counts["FIRST_PREMIUM"] == len(first_premiums)
    assert counts["EMISSION"] == 1
    assert counts["FIRST_PREMIUM"] == 1
    kinds = {row["kind"]: row for row in queue.data["items"]}
    assert kinds["REVIEW"]["action"]["code"] == "ASSIGN_TO_ME"
    assert kinds["EMISSION"]["entityId"] == approved["id"]
    assert kinds["FIRST_PREMIUM"]["entityId"] == pending["id"]

    only = _approver(tenant).get("/api/v1/work-queue", {"kind": "REVIEW"}).data
    assert {row["kind"] for row in only["items"]} == {"REVIEW"}
    assert {row["kind"]: row["count"] for row in only["counts"]} == counts
    assert submitted["id"] in {row["entityId"] for row in only["items"]}


@pytest.mark.django_db
def test_work_queue_respects_permissions(admin_client, tenant):
    _submitted(admin_client, suffix="F4")
    director = make_client(tenant_id=tenant.id, roles=["TECHNICAL_DIRECTOR"], scope="q360.read q360.approve", actor_id="dir-1")
    data = director.get("/api/v1/work-queue").data
    assert [row["kind"] for row in data["counts"]] == ["DISCOUNT"]


@pytest.mark.django_db
def test_returned_quote_is_named_and_queued_for_correction(admin_client, tenant):
    submitted, _, _ = _submitted(admin_client, suffix="F5")
    returned = _approver(tenant).post(
        f"/api/v1/quotes/{submitted['id']}/decision",
        {"decision": "RETURN", "reasonCode": "FALTA_QUESTIONARIO", "rowVersion": submitted["rowVersion"]}, format="json",
    )
    assert returned.status_code == 200, returned.data
    assert returned.data["status"] == "READY"
    assert returned.data["displayStatus"] == "RETURNED" and returned.data["statusLabel"] == "Devolvida"
    queue = admin_client.get("/api/v1/work-queue", {"kind": "RETURNED_QUOTE"}).data
    assert [row["entityId"] for row in queue["items"]] == [submitted["id"]]


@pytest.mark.django_db
def test_acceptance_becomes_an_emission_task_first_in_line(admin_client, tenant):
    from apps.customer_portal.application import requests_service
    from apps.foundation.application.context import CurrentActorProvider
    from apps.foundation.domain.actor import Actor
    from apps.foundation.domain.scopes import Scope
    from apps.foundation.domain.tenant import TenantId

    other = _approved_quote(admin_client, tenant, suffix="F6")
    accepted = _another_approved(admin_client, tenant, plan_id=other["planId"], suffix="F7")
    account, _ = CustomerAccount.all_tenants.get_or_create(tenant_id=tenant.id, email="holder@example.com")
    token = CurrentActorProvider.bind(Actor(
        actor_id="system", tenant_id=TenantId.parse(tenant.id), roles=frozenset(), scopes=frozenset(Scope),
    ))
    try:
        quote = Quote.objects.get(id=accepted["id"])
        requests_service._route_acceptance_to_emission(  # noqa: SLF001
            PortalRequest.objects.create(
                tenant_id=tenant.id, request_number="PED-ACC", customer_account_id=account.id,
                proposer_id=accepted["proposerId"], quote_id=accepted["id"], request_type="ACCEPT_QUOTE",
                subject="Aceitar", status="OPEN",
            ),
            quote,
        )
    finally:
        CurrentActorProvider.reset(token)
    items = _approver(tenant).get("/api/v1/work-queue", {"kind": "EMISSION"}).data["items"]
    by_id = {row["entityId"]: row for row in items}
    assert by_id[accepted["id"]]["statusLabel"] == "Aceite"
    assert by_id[other["id"]]["statusLabel"] == "Aprovada"
    assert admin_client.get(f"/api/v1/quotes/{accepted['id']}").data["displayStatus"] == "ACCEPTED"
    draft = admin_client.get(f"/api/v1/quotes/{accepted['id']}/policy-draft").data
    assert draft["acceptance"]["requestNumber"] == "PED-ACC"


# ---------------------------------------------------------------- pesquisa
@pytest.mark.django_db
def test_search_masks_the_nif_and_offers_actions(admin_client, tenant):
    quote, proposer, _ = _ready_quote(admin_client, suffix="S1")
    Quote.all_tenants.filter(id=quote["id"]).update(quote_number="COT-90001")
    data = admin_client.get("/api/v1/search", {"q": "923456"}).data
    client = next(g for g in data["groups"] if g["kind"] == "proposer")["items"][0]
    assert client["title"] == proposer["displayName"]
    assert client["maskedNif"].startswith("•••••")
    assert proposer["registrationNumber"] not in client["subtitle"]
    assert client["actions"][0]["code"] == "NEW_QUOTE"

    by_reference = admin_client.get("/api/v1/search", {"q": "90001"}).data
    assert next(g for g in by_reference["groups"] if g["kind"] == "quote")["items"][0]["statusLabel"] == "Rascunho"


@pytest.mark.django_db
def test_status_dictionary_lists_every_entity(admin_client):
    data = admin_client.get("/api/v1/status-dictionary").data
    assert {"status": "RETURNED", "label": "Devolvida"} in data["quote"]
    assert {"status": "ACTIVE", "label": "Ativa"} in data["policy"]
    assert [row["label"] for row in data["installment"]] == ["A aguardar", "Paga", "Em atraso", "Anulada"]


# --------------------------------------------------------- extrato bancário
def _statement(rows: list[str]) -> SimpleUploadedFile:
    return SimpleUploadedFile("extrato.csv", "\n".join(["Data;Valor;Referência;Descrição", *rows]).encode("utf-8"), content_type="text/csv")


@pytest.mark.django_db
def test_bank_statement_is_previewed_then_registered_once(admin_client, tenant):
    policy = _emit(tenant, _approved_quote(admin_client, tenant, suffix="B1"))
    number = policy["policyNumber"]
    rows = [
        f"2026-06-10;1.200,00;RF-1;Pagamento {number}",
        f"2026-06-10;1.200,00;RF-1;Pagamento {number}",
        f"2026-06-10;999,00;RF-2;Pagamento {number}",
        "2026-06-10;50,00;RF-3;Sem apólice",
        "ontem;50,00;RF-4;Data errada",
    ]
    approver = _approver(tenant)
    preview = approver.post("/api/v1/payment-reconciliations/preview", {"file": _statement(rows)}, format="multipart")
    assert preview.status_code == 200, preview.data
    statuses = [line["status"] for line in preview.data["lines"]]
    assert statuses == ["MATCHED", "DUPLICATE_IN_FILE", "AMOUNT_MISMATCH", "NO_POLICY", "INVALID"]
    assert preview.data["lines"][0]["installmentNos"] == [1]
    assert PremiumInstallment.all_tenants.get(policy_id=policy["id"], installment_no=1).status == "DUE"

    line = preview.data["lines"][0]
    payload = {"lines": [{
        "line": line["line"], "policyId": line["policyId"], "installmentNos": line["installmentNos"],
        "amount": line["amount"], "paidOn": line["paidOn"], "paymentReference": line["reference"],
    }]}
    result = approver.post("/api/v1/payment-reconciliations/commit", payload, format="json")
    assert result.status_code == 200, result.data
    assert len(result.data["registered"]) == 1 and result.data["failed"] == []
    assert admin_client.get(f"/api/v1/policies/{policy['id']}").data["status"] == "ACTIVE"

    second = approver.post("/api/v1/payment-reconciliations/preview", {"file": _statement(rows[:1])}, format="multipart")
    assert second.data["lines"][0]["status"] == "ALREADY_REGISTERED"


@pytest.mark.django_db
def test_bank_statement_needs_the_expected_columns(tenant):
    bad = SimpleUploadedFile("extrato.csv", b"a;b\n1;2\n", content_type="text/csv")
    response = _approver(tenant).post("/api/v1/payment-reconciliations/preview", {"file": bad}, format="multipart")
    assert response.status_code == 400


# ------------------------------------- uma transferência, várias prestações
def _now():
    """Pago hoje: um pagamento antigo deixaria a 2.ª prestação já vencida."""
    from django.utils import timezone

    return timezone.now().isoformat()


def _paid(admin_client, policy_id):
    rows = admin_client.get(f"/api/v1/policies/{policy_id}/installments").data
    return [row["installmentNo"] for row in rows if row["status"] == "PAID"]


@pytest.mark.django_db
def test_one_transfer_pays_consecutive_installments_of_a_pending_policy(admin_client, tenant):
    policy = _emit(tenant, _approved_quote(admin_client, tenant, suffix="M1"), frequency="TRIMESTRAL")
    options = admin_client.get(f"/api/v1/policies/{policy['id']}/payment-options").data
    assert [o["installmentNos"] for o in options["options"]] == [[1], [1, 2], [1, 2, 3], [1, 2, 3, 4]]
    two = options["options"][1]["total"]

    response = _approver(tenant).post(f"/api/v1/policies/{policy['id']}/payments", {
        "installmentNos": [1, 2], "amount": two, "paidAt": _now(), "paymentReference": "TRF-2P",
        "paymentMethod": "TRANSFERENCIA", "rowVersion": policy["rowVersion"],
    }, format="json")
    assert response.status_code == 200, response.data
    assert response.data["status"] == "ACTIVE"
    batch = {row["paymentBatchId"] for row in response.data["installments"]}
    assert len(batch) == 1 and None not in batch
    assert _paid(admin_client, policy["id"]) == [1, 2]
    assert [o["installmentNos"] for o in admin_client.get(f"/api/v1/policies/{policy['id']}/payment-options").data["options"]] == [[3], [3, 4]]


@pytest.mark.django_db
def test_allocation_is_all_or_nothing(admin_client, tenant):
    policy = _emit(tenant, _approved_quote(admin_client, tenant, suffix="M2"), frequency="TRIMESTRAL")
    options = admin_client.get(f"/api/v1/policies/{policy['id']}/payment-options").data["options"]
    base = {"paidAt": _now(), "paymentReference": "TRF-X", "rowVersion": policy["rowVersion"]}
    url = f"/api/v1/policies/{policy['id']}/payments"
    approver = _approver(tenant)

    assert approver.post(url, {**base, "installmentNos": [1, 2], "amount": "1.00"}, format="json").status_code == 400
    skipped = approver.post(url, {**base, "installmentNos": [1, 3], "amount": options[1]["total"]}, format="json")
    assert skipped.status_code == 409
    no_reference = {**base, "paymentReference": None, "installmentNos": [1, 2], "amount": options[1]["total"]}
    assert approver.post(url, no_reference, format="json").status_code == 400
    assert _paid(admin_client, policy["id"]) == []
    assert admin_client.get(f"/api/v1/policies/{policy['id']}").data["status"] == "PENDING_FIRST_PREMIUM"


@pytest.mark.django_db
def test_a_transfer_reference_cannot_be_reused_after_paying_several_installments(admin_client, tenant):
    first = _approved_quote(admin_client, tenant, suffix="M3")
    policy = _emit(tenant, first, frequency="TRIMESTRAL")
    options = admin_client.get(f"/api/v1/policies/{policy['id']}/payment-options").data["options"]
    url = f"/api/v1/policies/{policy['id']}/payments"
    done = _approver(tenant).post(url, {
        "installmentNos": [1, 2], "amount": options[1]["total"], "paidAt": _now(),
        "paymentReference": "TRF-UNICA", "rowVersion": policy["rowVersion"],
    }, format="json")
    assert done.status_code == 200, done.data
    again = _approver(tenant).post(url, {
        "installmentNos": [3], "amount": options[0]["total"], "paidAt": _now(), "paymentReference": "trf-unica",
    }, format="json")
    assert again.status_code == 409 and again.data["code"] == "PAYMENT-REFERENCE-DUPLICATE"
    assert _paid(admin_client, policy["id"]) == [1, 2]


@pytest.mark.django_db
def test_bank_statement_suggests_several_installments_for_confirmation(admin_client, tenant):
    policy = _emit(tenant, _approved_quote(admin_client, tenant, suffix="M4"), frequency="TRIMESTRAL")
    option = admin_client.get(f"/api/v1/policies/{policy['id']}/payment-options").data["options"][1]
    approver = _approver(tenant)
    file = _statement([f"{_now()[:10]};{option['total'].replace('.', ',')};TRF-M4;Pagamento {policy['policyNumber']}"])
    preview = approver.post("/api/v1/payment-reconciliations/preview", {"file": file}, format="multipart")
    line = preview.data["lines"][0]
    assert line["status"] == "MATCHED_MULTIPLE" and line["installmentNos"] == [1, 2]

    result = approver.post("/api/v1/payment-reconciliations/commit", {"lines": [{
        "line": line["line"], "policyId": line["policyId"], "installmentNos": line["installmentNos"],
        "amount": line["amount"], "paidOn": line["paidOn"], "paymentReference": line["reference"],
    }]}, format="json")
    assert result.status_code == 200, result.data
    assert result.data["registered"][0]["installmentNos"] == [1, 2]
    assert _paid(admin_client, policy["id"]) == [1, 2]


# ---------------------------------------------------------------- importação
def _workbook(rows) -> SimpleUploadedFile:
    import openpyxl

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["relationshipCode", "firstName", "lastName", "dateOfBirth", "sexCode", "externalReference"])
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    return SimpleUploadedFile("membros.xlsx", output.getvalue())


@pytest.mark.django_db
def test_import_reports_ready_duplicate_and_error_rows(admin_client, tenant):
    _, proposer, _ = _ready_quote(admin_client, suffix="I1")
    organisation = admin_client.post("/api/v1/proposers", {
        "proposerType": "ORGANISATION", "displayName": "Empresa Horizonte", "nif": "5417000000",
        "email": "geral@demo.q360.local", "phone": "+244900000001",
    }).data
    assert organisation.get("id"), organisation
    admin_client.post("/api/v1/members", {
        "firstName": "Rosa", "lastName": "Kiala", "proposerId": organisation["id"], "relationshipCode": "COLABORADOR",
        "dateOfBirth": "1980-02-02", "externalReference": "EX-1",
    })
    file = _workbook([
        ["COLABORADOR", "Rosa", "Kiala", "1980-02-02", "F", "EX-9"],
        ["COLABORADOR", "Manuel", "Kiala", "1982-03-03", "M", "EX-2"],
        ["COLABORADOR", "Manuel", "Kiala", "1982-03-03", "M", "EX-3"],
        ["COLABORADOR", "Sara", "Neto", "31/02/1990", "F", "EX-4"],
    ])
    uploaded = admin_client.post("/api/v1/member-imports", {"proposerId": organisation["id"], "file": file}, format="multipart")
    assert uploaded.status_code == 202, uploaded.data
    body = uploaded.data
    assert (body["validRows"], body["duplicateRows"], body["errorRows"]) == (1, 2, 1)
    problem = next(p for p in body["rowProblems"] if not p["duplicate"])
    assert problem["sheetRow"] == 5 and "não é uma data válida" in problem["message"]

    report = admin_client.get(f"/api/v1/member-imports/{body['id']}/error-report")
    assert report.status_code == 200 and report.content[:2] == b"PK"

    committed = admin_client.post(f"/api/v1/member-imports/{body['id']}/commit", {"confirm": True}, format="json")
    assert committed.status_code == 202, committed.data
    members = admin_client.get("/api/v1/members", {"proposerId": organisation["id"]}).data
    names = [m["firstName"] for m in members.get("items", members)]
    assert names.count("Rosa") == 1 and names.count("Manuel") == 1


def _household_workbook(rows) -> SimpleUploadedFile:
    import openpyxl

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["memberType", "relationshipCode", "firstName", "lastName", "dateOfBirth", "sexCode", "externalReference", "holderReference"])
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    return SimpleUploadedFile("colaboradores.xlsx", output.getvalue())


def _organisation(client, *, nif):
    created = client.post("/api/v1/proposers", {
        "proposerType": "ORGANISATION", "displayName": f"Empresa {nif}", "nif": nif,
        "email": "geral@demo.q360.local", "phone": "+244900000001",
    }).data
    assert created.get("id"), created
    return created


@pytest.mark.django_db
def test_household_import_keeps_valid_rows_and_never_duplicates_dependents(admin_client, tenant):
    organisation = _organisation(admin_client, nif="5417000001")
    rows = [
        ["COLABORADOR", "COLABORADOR", "Tomas", "Neto", "1980-02-02", "M", "C-1", None],
        ["DEPENDENTE", "CONJUGE", "Sara", "Neto", "1982-03-03", "F", None, "C-1"],
        ["COLABORADOR", "COLABORADOR", "Sem", "Data", "31/02/1990", "M", "C-2", None],
        ["DEPENDENTE", "FILHO", "Orfa", "Data", "2015-03-03", "F", None, "C-2"],
    ]
    url = "/api/v1/member-imports"
    first = admin_client.post(url, {"proposerId": organisation["id"], "file": _household_workbook(rows)}, format="multipart").data
    assert (first["validRows"], first["errorRows"]) == (2, 2)
    committed = admin_client.post(f"{url}/{first['id']}/commit", {"confirm": True}, format="json")
    assert committed.status_code == 202, committed.data
    names = [m["firstName"] for m in admin_client.get("/api/v1/members", {"proposerId": organisation["id"]}).data["items"]]
    assert sorted(names) == ["Sara", "Tomas"]

    second = admin_client.post(url, {"proposerId": organisation["id"], "file": _household_workbook(rows[:2])}, format="multipart").data
    assert second["validRows"] == 0 and second["duplicateRows"] == 1
    refused = admin_client.post(f"{url}/{second['id']}/commit", {"confirm": True}, format="json")
    assert refused.status_code >= 400
    names = [m["firstName"] for m in admin_client.get("/api/v1/members", {"proposerId": organisation["id"]}).data["items"]]
    assert sorted(names) == ["Sara", "Tomas"]


# ------------------------------------------------------------------ inclusão
@pytest.mark.django_db
def test_inclusion_preview_calculates_without_saving(admin_client, tenant):
    quote = _approved_quote(admin_client, tenant, suffix="N1")
    policy = _emit(tenant, quote, payment=_PAYMENT)
    newcomer = admin_client.post("/api/v1/members", {
        "firstName": "Joana", "proposerId": quote["proposerId"], "relationshipCode": "CONJUGE", "dateOfBirth": "1992-01-01",
    }).data
    before = Quote.all_tenants.filter(tenant_id=tenant.id).count()
    url = f"/api/v1/policies/{policy['id']}/endorsements/inclusions/preview"
    inclusion_date = __import__("datetime").date.today().isoformat()
    response = admin_client.post(url, {"inclusionDate": inclusion_date, "memberIds": [newcomer["id"]]}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["calculated"] is True
    assert Quote.all_tenants.filter(tenant_id=tenant.id).count() == before

    duplicate = admin_client.post(url, {"inclusionDate": inclusion_date, "memberIds": [quote["memberId"]]}, format="json")
    assert duplicate.status_code >= 400
    assert Quote.all_tenants.filter(tenant_id=tenant.id).count() == before


# ------------------------------------------------------------------ renovação
@pytest.mark.django_db
def test_renewals_are_listed_and_created_in_batch(admin_client, tenant):
    import datetime

    from apps.policy.infrastructure.models import Policy

    policy = _emit(tenant, _approved_quote(admin_client, tenant, suffix="V1"), payment=_PAYMENT)
    end = datetime.date.today() + datetime.timedelta(days=10)
    Policy.all_tenants.filter(id=policy["id"]).update(end_date=end)
    quotes_before = Quote.all_tenants.filter(tenant_id=tenant.id).count()

    listed = admin_client.get("/api/v1/renewals/due", {"days": 30})
    assert listed.status_code == 200, listed.data
    row = listed.data["items"][0]
    assert row["policyId"] == policy["id"] and row["daysToEnd"] == 10 and row["currentPremium"] == "1200.00"
    assert row["proposedPremium"] is not None
    assert Quote.all_tenants.filter(tenant_id=tenant.id).count() == quotes_before, "a prévia não pode gravar nada"

    missing = uuid.uuid4()
    created = admin_client.post("/api/v1/quotes/renewals/batch", {"policyIds": [policy["id"], str(missing)]}, format="json")
    assert created.status_code == 200, created.data
    assert [c["policyId"] for c in created.data["created"]] == [policy["id"]]
    assert created.data["failed"][0]["policyId"] == str(missing)

    again = admin_client.post("/api/v1/quotes/renewals/batch", {"policyIds": [policy["id"]]}, format="json")
    assert again.data["created"] == [] and "em aberto" in again.data["failed"][0]["reason"]
    assert admin_client.get("/api/v1/renewals/due", {"days": 30}).data["items"][0]["renewalQuoteId"] is not None
