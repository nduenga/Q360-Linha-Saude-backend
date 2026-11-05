"""Diagnóstico do email: configuração incompleta, recusa do servidor e mensagem real."""
from __future__ import annotations

from unittest import mock

import pytest
from django.core.management import CommandError, call_command

from apps.customer_portal.application.email_config import check_email_settings, email_config_problems

GOOD = {
    "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend", "EMAIL_HOST": "smtp.exemplo.ao",
    "EMAIL_HOST_USER": "convites@exemplo.ao", "EMAIL_HOST_PASSWORD": "x",
    "CUSTOMER_PORTAL_EMAIL_FROM": "convites@exemplo.ao", "CUSTOMER_PORTAL_URL": "https://app.exemplo.ao/portal-cliente",
}


@pytest.fixture
def smtp(settings):
    for key, value in GOOD.items():
        setattr(settings, key, value)
    return settings


def test_complete_configuration_has_no_problems(smtp):
    assert email_config_problems() == []


@pytest.mark.parametrize(("key", "value", "text"), [
    ("EMAIL_HOST", "", "EMAIL_HOST"),
    ("EMAIL_HOST_PASSWORD", "", "EMAIL_HOST_USER"),
    ("CUSTOMER_PORTAL_EMAIL_FROM", "no-reply@q360.example", "valor de exemplo"),
    ("CUSTOMER_PORTAL_URL", "http://localhost:5173/portal-cliente", "CUSTOMER_PORTAL_URL"),
])
def test_each_gap_is_reported(smtp, key, value, text):
    setattr(smtp, key, value)
    assert any(text in problem for problem in email_config_problems())
    with pytest.raises(CommandError, match="Configuração incompleta"):
        call_command("check_email")


def test_console_backend_is_reported_by_the_command_but_not_at_startup(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    assert any("não saem" in problem for problem in email_config_problems())
    assert check_email_settings(None) == []


def test_startup_warning_in_production_without_a_portal_url(smtp):
    smtp.DEBUG = False
    smtp.CUSTOMER_PORTAL_URL = "http://localhost:5173/portal-cliente"
    assert [warning.id for warning in check_email_settings(None)] == ["q360.W001"]


def test_server_rejection_is_an_error(smtp):
    with mock.patch("django.core.mail.backends.smtp.EmailBackend.open", side_effect=OSError("recusado")):
        with pytest.raises(CommandError, match="recusado"):
            call_command("check_email")


def test_to_sends_a_real_message(smtp):
    connection = mock.MagicMock()
    with mock.patch("apps.customer_portal.management.commands.check_email.get_connection", return_value=connection), \
         mock.patch("apps.customer_portal.management.commands.check_email.send_mail") as send:
        call_command("check_email", to="teste@exemplo.ao")
    assert send.call_args.kwargs["recipient_list"] == ["teste@exemplo.ao"]
    connection.open.assert_called_once()
