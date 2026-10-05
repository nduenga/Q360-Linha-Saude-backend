"""Login por email + palavra-passe do Portal Cliente: primeiro acesso por código
enviado ao email do registo, «esqueci-me», login e bloqueio."""
from __future__ import annotations

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.customer_portal.domain.password import PortalPasswordInvalidError, mask_email, validate_password_strength
from tests.customer_portal.test_self_service_api import _EMAIL, _set_quote, _setup_active_policy_with_member

GOOD = "uma-frase-bem-longa-1"
NEW = "outra-frase-mais-longa-2"


@pytest.fixture(autouse=True)
def _no_ip_limit(settings):
    settings.CUSTOMER_PORTAL_LOGIN_RATE_LIMIT_PER_IP = 0


def _url(tenant, path: str) -> str:
    return f"/api/v1/customer-portal/{tenant.id}/auth/{path}"


def _code() -> str:
    return mail.outbox[-1].body.split(": ", 1)[1].splitlines()[0].strip()


def _customer(admin_client, tenant, number="APO-L-001", reg="951111111LA011"):
    return _setup_active_policy_with_member(admin_client, tenant, policy_number=number, registration_number=reg)


def _first_access(tenant, scope, password=GOOD, reference=None):
    client = APIClient()
    ref = reference or scope["policyNumber"]
    asked = client.post(_url(tenant, "first-access/request"), {"reference": ref, "registrationNumber": scope["registrationNumber"]}, format="json")
    assert asked.status_code == 202, asked.data
    return client.post(
        _url(tenant, "first-access/confirm"),
        {"reference": ref, "registrationNumber": scope["registrationNumber"], "otp": _code(), "password": password},
        format="json",
    )


def _login(tenant, email=_EMAIL, password=GOOD):
    return APIClient().post(_url(tenant, "login"), {"email": email, "password": password}, format="json")


# ------------------------------------------------------------ domínio puro
def test_password_strength_rules():
    for weak in ("curta", "1234567890", "aaaaaaaaaaaa", "password123", "9876543210", "joaosilva-123"):
        with pytest.raises(PortalPasswordInvalidError):
            validate_password_strength(weak, email="joaosilva@x.com")
    validate_password_strength("uma-frase-bem-longa-1", email="joaosilva@x.com")


def test_mask_email():
    assert mask_email("joao.silva@gmail.com") == "jo***@gmail.com"
    assert mask_email("ab@x.com") == "a***@x.com"


# --------------------------------------------------------- primeiro acesso
@pytest.mark.django_db
def test_first_access_sends_the_code_to_the_email_on_file_and_sets_the_password(admin_client, tenant):
    scope = _customer(admin_client, tenant)
    asked = APIClient().post(
        _url(tenant, "first-access/request"),
        {"reference": scope["policyNumber"], "registrationNumber": scope["registrationNumber"]}, format="json",
    )
    assert asked.status_code == 202, asked.data
    assert asked.data == {"maskedEmail": mask_email(_EMAIL)}
    assert mail.outbox[-1].to == [_EMAIL]

    confirmed = _first_access(tenant, scope)
    assert confirmed.status_code == 200, confirmed.data
    assert confirmed.data["accessToken"]

    # the account only ever has the email on file, and the password works
    logged = _login(tenant)
    assert logged.status_code == 200, logged.data
    me = APIClient()
    me.credentials(HTTP_AUTHORIZATION=f"Bearer {logged.data['accessToken']}")
    assert [p["policy"]["policyNumber"] for p in me.get("/api/v1/customer-portal/me").data["policies"]] == [scope["policyNumber"]]


@pytest.mark.django_db
def test_first_access_accepts_a_quote_number_too(admin_client, tenant):
    scope = _customer(admin_client, tenant, "APO-L-002", "952222222LA022")
    _set_quote(scope, status="APPROVED", quote_number="Q-L-002")
    assert _first_access(tenant, scope, reference="Q-L-002").status_code == 200


@pytest.mark.django_db
def test_first_access_rejects_wrong_reference_document_and_missing_email(admin_client, tenant):
    from apps.client.infrastructure.models import Proposer

    scope = _customer(admin_client, tenant, "APO-L-003", "953333333LA033")
    client = APIClient()
    url = _url(tenant, "first-access/request")
    assert client.post(url, {"reference": "NOPE", "registrationNumber": scope["registrationNumber"]}, format="json").status_code == 404
    assert client.post(url, {"reference": scope["policyNumber"], "registrationNumber": "0000"}, format="json").status_code == 401

    Proposer.all_tenants.filter(id=scope["proposerId"]).update(email=None)
    no_email = client.post(url, {"reference": scope["policyNumber"], "registrationNumber": scope["registrationNumber"]}, format="json")
    assert no_email.status_code == 409 and no_email.data["code"] == "PORTAL-NO-EMAIL"
    assert mail.outbox == []


@pytest.mark.django_db
def test_a_weak_password_does_not_burn_the_code_and_a_wrong_code_fails(admin_client, tenant):
    scope = _customer(admin_client, tenant, "APO-L-004", "954444444LA044")
    client = APIClient()
    body = {"reference": scope["policyNumber"], "registrationNumber": scope["registrationNumber"]}
    client.post(_url(tenant, "first-access/request"), body, format="json")
    code = _code()

    weak = client.post(_url(tenant, "first-access/confirm"), {**body, "otp": code, "password": "curta"}, format="json")
    assert weak.status_code == 400
    wrong = client.post(_url(tenant, "first-access/confirm"), {**body, "otp": "000000" if code != "000000" else "111111", "password": GOOD}, format="json")
    assert wrong.status_code == 401
    ok = client.post(_url(tenant, "first-access/confirm"), {**body, "otp": code, "password": GOOD}, format="json")
    assert ok.status_code == 200, ok.data
    # a code is single-use
    assert client.post(_url(tenant, "first-access/confirm"), {**body, "otp": code, "password": NEW}, format="json").status_code == 401


# ------------------------------------------------------------------ login
@pytest.mark.django_db
def test_login_is_generic_about_unknown_emails_and_wrong_passwords_and_locks(admin_client, tenant):
    scope = _customer(admin_client, tenant, "APO-L-005", "955555555LA055")
    assert _first_access(tenant, scope).status_code == 200

    unknown = _login(tenant, email="ninguem@example.com")
    wrong = _login(tenant, password="palavra-errada-123")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.data["detail"] == wrong.data["detail"]

    for _ in range(3):
        assert _login(tenant, password="palavra-errada-123").status_code == 401
    assert _login(tenant, password="palavra-errada-123").status_code == 423  # 5th failure locks
    assert _login(tenant).status_code == 423  # even the right password, while locked


@pytest.mark.django_db
def test_login_is_case_insensitive_on_the_email(admin_client, tenant):
    scope = _customer(admin_client, tenant, "APO-L-006", "956666666LA066")
    _first_access(tenant, scope)
    assert _login(tenant, email=_EMAIL.upper()).status_code == 200


@pytest.mark.django_db
def test_an_account_without_a_password_cannot_log_in(admin_client, tenant):
    scope = _customer(admin_client, tenant, "APO-L-007", "957777777LA077")
    APIClient().post(_url(tenant, "first-access/request"),
                     {"reference": scope["policyNumber"], "registrationNumber": scope["registrationNumber"]}, format="json")
    assert _login(tenant).status_code == 401


# ------------------------------------------------------------ esqueci-me
@pytest.mark.django_db
def test_password_reset_flow(admin_client, tenant):
    scope = _customer(admin_client, tenant, "APO-L-008", "958888888LA088")
    _first_access(tenant, scope)
    client = APIClient()

    sent_before = len(mail.outbox)
    assert client.post(_url(tenant, "password-reset/request"), {"email": "ninguem@example.com"}, format="json").status_code == 202
    assert len(mail.outbox) == sent_before  # no email, and no way to tell

    assert client.post(_url(tenant, "password-reset/request"), {"email": _EMAIL}, format="json").status_code == 202
    assert len(mail.outbox) == sent_before + 1
    done = client.post(_url(tenant, "password-reset/confirm"), {"email": _EMAIL, "otp": _code(), "password": NEW}, format="json")
    assert done.status_code == 200, done.data
    assert _login(tenant, password=GOOD).status_code == 401
    assert _login(tenant, password=NEW).status_code == 200


# --------------------------------------------- separação entre os dois logins
@pytest.mark.django_db
def test_a_set_password_code_cannot_be_used_by_the_legacy_otp_login(admin_client, tenant):
    scope = _customer(admin_client, tenant, "APO-L-009", "959999999LA099")
    client = APIClient()
    client.post(_url(tenant, "first-access/request"),
                {"reference": scope["policyNumber"], "registrationNumber": scope["registrationNumber"]}, format="json")
    legacy = client.post(
        _url(tenant, "verify-otp"),
        {"policyNumber": scope["policyNumber"], "registrationNumber": scope["registrationNumber"], "email": _EMAIL, "otp": _code()},
        format="json",
    )
    assert legacy.status_code == 401


@pytest.mark.django_db
def test_legacy_login_can_be_switched_off(admin_client, tenant, settings):
    scope = _customer(admin_client, tenant, "APO-L-010", "960000000LA000")
    settings.CUSTOMER_PORTAL_LEGACY_LOGIN_ENABLED = False
    body = {"policyNumber": scope["policyNumber"], "registrationNumber": scope["registrationNumber"], "email": _EMAIL}
    assert APIClient().post(_url(tenant, "request-access"), body, format="json").status_code == 404
    assert APIClient().post(_url(tenant, "verify-otp"), {**body, "otp": "123456"}, format="json").status_code == 404
    # the new login keeps working
    assert _first_access(tenant, scope).status_code == 200
