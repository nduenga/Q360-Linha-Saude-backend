"""Deteta a configuração de email que impede os convites de chegarem ao cliente."""
from __future__ import annotations

from django.conf import settings
from django.core import checks


def email_config_problems() -> list[str]:
    backend = settings.EMAIL_BACKEND
    problems = []
    if "smtp" not in backend:
        problems.append(f"EMAIL_BACKEND é {backend}: as mensagens não saem para a internet.")
    elif not settings.EMAIL_HOST:
        problems.append("EMAIL_HOST está vazio: não há servidor de email configurado.")
    elif bool(settings.EMAIL_HOST_USER) != bool(settings.EMAIL_HOST_PASSWORD):
        problems.append("EMAIL_HOST_USER e EMAIL_HOST_PASSWORD têm de ser definidos em conjunto.")
    if settings.CUSTOMER_PORTAL_EMAIL_FROM.endswith(".example"):
        problems.append("CUSTOMER_PORTAL_EMAIL_FROM ainda tem o valor de exemplo.")
    if not settings.DEBUG and ("localhost" in settings.CUSTOMER_PORTAL_URL or "127.0.0.1" in settings.CUSTOMER_PORTAL_URL):
        problems.append("CUSTOMER_PORTAL_URL aponta para esta máquina: o link do convite não abre no cliente.")
    return problems


def check_email_settings(app_configs, **kwargs) -> list[checks.Warning]:
    """Aviso de arranque só em produção: em desenvolvimento e testes não sair email é o esperado."""
    if settings.DEBUG or "smtp" not in settings.EMAIL_BACKEND:
        return []
    return [
        checks.Warning(problem, hint="Confirme com: python manage.py check_email", id=f"q360.W00{index}")
        for index, problem in enumerate(email_config_problems(), start=1)
    ]
