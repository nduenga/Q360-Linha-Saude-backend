"""Uma conta bloqueada por tentativas falhadas aparece como bloqueada na
lista de utilizadores (antes mostrava só «ATIVO») e o administrador pode
desbloqueá-la sem mudar a palavra-passe."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from tests.platform_admin.test_platform_admin import NEW_TENANT, SECRET, _admin, _client, _staff_login


@pytest.fixture(autouse=True)
def _keys(settings):
    settings.PLATFORM_ADMIN_JWT_SIGNING_KEY = SECRET
    settings.Q360_JWT_SIGNING_KEY = "staff-tests-signing-secret-32-bytes-minimum"
    settings.Q360_STAFF_LOGIN_RATE_LIMIT = 0


@pytest.mark.django_db
def test_locked_account_is_shown_and_can_be_unlocked():
    _admin()
    made = _client().post("/api/v1/platform/tenants", NEW_TENANT, format="json").data
    logged = _staff_login("ana@acme.ao", made["temporaryPassword"])
    admin = APIClient()
    admin.credentials(HTTP_AUTHORIZATION=f"Bearer {logged.data['accessToken']}")
    created = admin.post("/api/v1/admin/staff-accounts", {"email": "rui@acme.ao", "name": "Rui", "roles": ["SUBSCRIBER"],
                                                         "password": "Senha-Forte-2026!"}, format="json")
    assert created.status_code == 201, created.data
    assert created.data["lockedUntil"] is None

    for _ in range(5):
        _staff_login("rui@acme.ao", "errada")
    assert _staff_login("rui@acme.ao", "Senha-Forte-2026!").status_code != 200
    listed = {a["email"]: a for a in admin.get("/api/v1/admin/staff-accounts").data}
    assert listed["rui@acme.ao"]["status"] == "ACTIVE" and listed["rui@acme.ao"]["lockedUntil"]

    assert admin.post(f"/api/v1/admin/staff-accounts/{created.data['id']}/unlock").status_code == 204
    listed = {a["email"]: a for a in admin.get("/api/v1/admin/staff-accounts").data}
    assert listed["rui@acme.ao"]["lockedUntil"] is None
    assert _staff_login("rui@acme.ao", "Senha-Forte-2026!").status_code == 200
