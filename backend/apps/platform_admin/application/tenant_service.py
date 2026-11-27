"""Ciclo de vida dos tenants (empresas clientes), feito pela plataforma.

Criar um tenant cria, numa só transação, o tenant, os seus dados de empresa
e o primeiro ADMIN com palavra-passe temporária (devolvida uma única vez).
O tenant nasce vazio e isolado: produtos, planos, clientes, cotações e
configuração de negócio são só dele (o catálogo de coberturas de mercado é
criado quando o tenant o usa pela primeira vez)."""
from __future__ import annotations

import datetime
import logging
import secrets
import uuid
from typing import Any

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.foundation.application import tenant_status
from apps.foundation.infrastructure.models import Tenant
from apps.platform_admin.application import email_settings, tenant_settings
from apps.platform_admin.application.audit_service import record_platform_audit
from apps.platform_admin.domain.errors import PlatformConflictError, PlatformNotFoundError
from apps.staff_accounts.application import credential_mail
from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole

logger = logging.getLogger(__name__)
PROFILE_FIELDS = ("nif", "email", "phone", "address", "country", "notes")


def code_from_name(name: str) -> str:
    """Código do tenant a partir do nome: minúsculas, sem acentos, palavras
    separadas por «-» (p.ex. «Protteja Seguros, S.A.» → «protteja-seguros-s-a»).
    Se já existir, acrescenta -2, -3… para ficar único na plataforma."""
    import re
    import unicodedata

    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:45].strip("-")
    if len(base) < 3:
        base = (base + "-seguradora").strip("-")
    code, n = base, 2
    while Tenant.objects.filter(code=code).exists():
        code, n = f"{base}-{n}", n + 1
    return code


def _temporary_password() -> str:
    return secrets.token_urlsafe(18)


def _clean_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    return {k: v for k, v in (profile or {}).items() if k in PROFILE_FIELDS and v not in (None, "")}


def _get(tenant_id) -> Tenant:
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        raise PlatformNotFoundError("Tenant não encontrado")
    return tenant


def _create_admin(tenant_id, email: str, name: str) -> tuple[StaffAccount, str]:
    password = _temporary_password()
    admin = StaffAccount.all_tenants.create(
        id=uuid.uuid4(), tenant_id=tenant_id, email=email, name=name, password_hash=make_password(password),
        status=StaffAccount.ACTIVE, row_version=0,
    )
    StaffAccountRole.all_tenants.create(id=uuid.uuid4(), tenant_id=tenant_id, staff_account_id=admin.id, role="ADMIN")
    return admin, password


@transaction.atomic
def create_tenant(*, actor_id, code, name, profile, admin_email, admin_name, correlation_id, email_settings_data=None):
    # O login do staff é só por email: o email é único em toda a plataforma.
    if StaffAccount.all_tenants.filter(email__iexact=admin_email).exists():
        raise PlatformConflictError("O email do administrador já existe na plataforma")
    code = (code or "").strip().lower() or code_from_name(name)
    try:
        with transaction.atomic():
            tenant = Tenant.objects.create(
                id=uuid.uuid4(), code=code, name=name, status="ACTIVE", row_version=0, profile_json=_clean_profile(profile)
            )
            admin, password = _create_admin(tenant.id, admin_email, admin_name)
    except IntegrityError as exc:
        raise PlatformConflictError("O código do tenant ou o email do administrador já existe") from exc
    tenant.email_settings_warning = None  # type: ignore[attr-defined]
    if email_settings_data:
        # SMTP da seguradora definido na criação: dados inválidos recusam tudo (nada fica criado);
        # um servidor que não responde cria o tenant, deixa o SMTP sem uso e avisa.
        saved = email_settings.save(tenant_id=tenant.id, data=email_settings_data, actor_id=actor_id,
                                    correlation_id=correlation_id)
        if not saved.last_test_ok:
            tenant.email_settings_warning = (  # type: ignore[attr-defined]
                "O servidor de email indicado não respondeu ao teste e não está a ser usado: "
                f"{saved.last_test_error}. Corrija-o no detalhe da seguradora."
            )
    credential_mail.send_welcome_email(
        to_email=admin.email, name=admin.name, password=password, tenant_name=tenant.name,
        account_id=str(admin.id), tenant_id=tenant.id,
    )
    record_platform_audit(
        actor_id=actor_id, action="platform.tenant_created", entity_type="Tenant", entity_id=str(tenant.id),
        correlation_id=correlation_id,
        metadata={"tenantCode": tenant.code, "tenantName": tenant.name, "adminId": str(admin.id), "adminEmail": admin.email},
    )
    return tenant, admin, password


def list_tenants(*, actor_id, correlation_id, status: str | None = None, search: str | None = None):
    qs = Tenant.objects.all().order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(name__icontains=search) | qs.filter(code__icontains=search)
    # Consultar a lista não altera nada: não se regista na auditoria (enchia o
    # trilho de eventos sem valor e escondia as alterações que importam).
    return list(qs)


def tenant_detail(*, tenant_id) -> tuple[Tenant, list[StaffAccount], dict[str, int]]:
    tenant = _get(tenant_id)
    accounts = list(StaffAccount.all_tenants.filter(tenant_id=tenant.id).order_by("created_at"))
    roles: dict[Any, list[str]] = {}
    for row in StaffAccountRole.all_tenants.filter(tenant_id=tenant.id):
        roles.setdefault(row.staff_account_id, []).append(row.role)
    for account in accounts:
        account.roles_list = sorted(roles.get(account.id, []))  # type: ignore[attr-defined]
    stats = {
        "staffAccounts": len(accounts),
        "activeStaffAccounts": sum(1 for a in accounts if a.status == StaffAccount.ACTIVE),
    }
    return tenant, accounts, stats


@transaction.atomic
def update_tenant(*, actor_id, tenant_id, name=None, profile=None, status=None, correlation_id=None,
                  suspension_reason=None, reactivate_on=None) -> Tenant:
    tenant = _get(tenant_id)
    changes: dict[str, Any] = {}
    before = {"name": tenant.name, "profile": dict(tenant.profile_json or {}), "status": tenant.status}
    settings = dict(tenant.settings_json or {})
    if status is not None and status != tenant.status:
        if status == "SUSPENDED":
            reason = (suspension_reason or "").strip()
            if len(reason) < 10:
                raise PlatformConflictError("Indique o motivo da suspensão (pelo menos 10 caracteres).")
            if reactivate_on is not None and reactivate_on <= timezone.localdate():
                raise PlatformConflictError("A data de reativação tem de ser no futuro.")
            settings["suspension"] = {
                "reason": reason, "reactivateOn": reactivate_on.isoformat() if reactivate_on else None,
                "suspendedAt": timezone.now().isoformat(), "suspendedBy": str(actor_id),
            }
            changes["suspensionReason"] = reason
            changes["reactivateOn"] = settings["suspension"]["reactivateOn"]
        elif tenant.status == "SUSPENDED":
            settings["suspension"] = None
    tenant.settings_json = settings
    if name is not None:
        tenant.name = name.strip()
        changes["name"] = tenant.name
    if profile is not None:
        tenant.profile_json = {**(tenant.profile_json or {}), **_clean_profile(profile)}
        changes["profile"] = sorted(_clean_profile(profile))
    old_status = tenant.status
    if status is not None and status != old_status:
        tenant.status = status
        changes["oldStatus"], changes["newStatus"] = old_status, status
    Tenant.objects.filter(id=tenant.id).update(
        name=tenant.name, profile_json=tenant.profile_json, status=tenant.status, settings_json=tenant.settings_json,
        updated_at=timezone.now(), row_version=tenant.row_version + 1,
    )
    tenant.row_version += 1
    tenant_status.invalidate(tenant.id)
    tenant_settings.invalidate(tenant.id)
    action = "platform.tenant_status_changed" if "newStatus" in changes else "platform.tenant_updated"
    after = {"name": tenant.name, "profile": dict(tenant.profile_json or {}), "status": tenant.status}
    record_platform_audit(
        actor_id=actor_id, action=action, entity_type="Tenant", entity_id=str(tenant.id),
        correlation_id=correlation_id, metadata={**changes, "before": before, "after": after},
    )
    if "newStatus" in changes:
        _notify_status_change(tenant, old_status=changes["oldStatus"])
    return tenant


# ------------------------------------------------------------ avisos por email
def _admin_emails(tenant_id) -> list[str]:
    admin_ids = StaffAccountRole.all_tenants.filter(tenant_id=tenant_id, role="ADMIN").values_list(
        "staff_account_id", flat=True
    )
    return list(
        StaffAccount.all_tenants.filter(id__in=list(admin_ids), status=StaffAccount.ACTIVE).values_list("email", flat=True)
    )


def _notify_status_change(tenant: Tenant, *, old_status: str) -> None:
    """Avisa os administradores da seguradora (depois do commit). Uma falha
    no email não desfaz a alteração: fica no log e na auditoria."""
    recipients = _admin_emails(tenant.id)
    if not recipients:
        return
    suspension = tenant_settings.settings_of(tenant).get("suspension") or {}
    if tenant.status == "SUSPENDED":
        subject = "O acesso da sua seguradora ao Q360 foi suspenso"
        until = suspension.get("reactivateOn")
        when = (f"O acesso volta automaticamente a {datetime.date.fromisoformat(until).strftime('%d/%m/%Y')}."
                if until else "O acesso volta quando a plataforma reativar a seguradora.")
        body = (f"Olá,\n\nO acesso de {tenant.name} ao Q360 foi suspenso.\n\n"
                f"Motivo: {suspension.get('reason')}\n\n{when}\n\n"
                "Para esclarecimentos, contacte a equipa da plataforma Q360.")
    elif tenant.status == "ACTIVE" and old_status != "ACTIVE":
        subject = "O acesso da sua seguradora ao Q360 foi reativado"
        body = f"Olá,\n\nO acesso de {tenant.name} ao Q360 está de novo ativo. Já pode entrar normalmente."
    else:
        subject = "O acesso da sua seguradora ao Q360 foi desativado"
        body = f"Olá,\n\nO acesso de {tenant.name} ao Q360 foi desativado. Contacte a equipa da plataforma Q360."

    def _send() -> None:
        from apps.customer_portal.infrastructure.email_sender import send_mail, sender

        try:
            send_mail(subject=subject, message=body, from_email=sender(tenant.name), recipient_list=recipients,
                      fail_silently=False, tenant_id=tenant.id)
        except Exception as exc:  # noqa: BLE001 - a mudança de estado não depende do email
            logger.exception("Falha ao avisar os administradores da seguradora %s", tenant.id)
            record_platform_audit(actor_id="SYSTEM", action="platform.tenant_notice_failed", entity_type="Tenant",
                                  entity_id=str(tenant.id), metadata={"reason": type(exc).__name__})
        else:
            record_platform_audit(actor_id="SYSTEM", action="platform.tenant_notice_sent", entity_type="Tenant",
                                  entity_id=str(tenant.id), metadata={"recipients": len(recipients), "status": tenant.status})

    transaction.on_commit(_send)


def reactivate_due_tenants(*, today: datetime.date | None = None) -> list[str]:
    """Tarefa diária: reativa as seguradoras suspensas cuja data de reativação chegou."""
    today = today or timezone.localdate()
    reactivated = []
    for tenant in Tenant.objects.filter(status="SUSPENDED"):
        until = (tenant_settings.settings_of(tenant).get("suspension") or {}).get("reactivateOn")
        if until and datetime.date.fromisoformat(until) <= today:
            update_tenant(actor_id="SYSTEM", tenant_id=tenant.id, status="ACTIVE")
            reactivated.append(tenant.code)
    return reactivated


# ------------------------------------------------- identidade visual e limites
@transaction.atomic
def update_tenant_settings(*, actor_id, tenant_id, branding=None, limits=None, correlation_id=None) -> Tenant:
    tenant = _get(tenant_id)
    current = tenant_settings.settings_of(tenant)
    stored = dict(tenant.settings_json or {})
    before = {"branding": {k: v for k, v in current["branding"].items() if k != "logo"}, "limits": current["limits"]}
    try:
        if branding is not None:
            stored["branding"] = {**(stored.get("branding") or {}), **tenant_settings.validate_branding(branding)}
        if limits is not None:
            clean = tenant_settings.validate_limits(limits)
            merged = {**(stored.get("limits") or {}), **clean}
            if "modules" in clean:
                merged["modules"] = {**((stored.get("limits") or {}).get("modules") or {}), **clean["modules"]}
            stored["limits"] = merged
    except tenant_settings.TenantSettingsError as exc:
        raise PlatformConflictError(str(exc)) from exc
    Tenant.objects.filter(id=tenant.id).update(settings_json=stored, updated_at=timezone.now())
    tenant.settings_json = stored
    tenant_settings.invalidate(tenant.id)
    after_all = tenant_settings.settings_of(tenant)
    after = {"branding": {k: v for k, v in after_all["branding"].items() if k != "logo"}, "limits": after_all["limits"]}
    record_platform_audit(actor_id=actor_id, action="platform.tenant_settings_updated", entity_type="Tenant",
                          entity_id=str(tenant.id), correlation_id=correlation_id,
                          metadata={"before": before, "after": after})
    return tenant


@transaction.atomic
def upload_tenant_logo(*, actor_id, tenant_id, data: bytes, content_type: str, correlation_id=None) -> Tenant:
    tenant = _get(tenant_id)
    try:
        key = tenant_settings.store_logo(tenant, data, content_type)
    except tenant_settings.TenantSettingsError as exc:
        raise PlatformConflictError(str(exc)) from exc
    stored = dict(tenant.settings_json or {})
    stored["branding"] = {**(stored.get("branding") or {}), "logo": key}
    Tenant.objects.filter(id=tenant.id).update(settings_json=stored, updated_at=timezone.now())
    tenant.settings_json = stored
    tenant_settings.invalidate(tenant.id)
    record_platform_audit(actor_id=actor_id, action="platform.tenant_logo_uploaded", entity_type="Tenant",
                          entity_id=str(tenant.id), correlation_id=correlation_id,
                          metadata={"contentType": content_type, "bytes": len(data)})
    return tenant


# ------------------------------------------------------- saúde e arranque
def _month_start() -> datetime.datetime:
    now = timezone.localtime()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def tenant_health(*, tenant_id) -> dict[str, Any]:
    """Painel de saúde da seguradora e lista de arranque (o estado de cada passo)."""
    from apps.business_config.infrastructure.models import BusinessConfiguration
    from apps.customer_portal.application.email_config import email_config_problems
    from apps.policy.infrastructure.models import Policy
    from apps.pricing.infrastructure.models import RatingTable
    from apps.product.infrastructure.models import PricingParameterSet, Product
    from apps.quote.infrastructure.models import DocumentTemplateVersion, Quote

    tenant = _get(tenant_id)
    accounts = StaffAccount.all_tenants.filter(tenant_id=tenant.id)
    admin_ids = set(StaffAccountRole.all_tenants.filter(tenant_id=tenant.id, role="ADMIN")
                    .values_list("staff_account_id", flat=True))
    admins = [a for a in accounts if a.id in admin_ids]
    last_login = max((a.last_login_at for a in accounts if a.last_login_at), default=None)
    month = _month_start()
    profile = tenant.profile_json or {}
    settings = tenant_settings.settings_of(tenant)

    tariff = (
        RatingTable.all_tenants.filter(tenant_id=tenant.id, status="PUBLISHED").exists()
        or PricingParameterSet.all_tenants.filter(tenant_id=tenant.id, status="PUBLISHED").exists()
        or BusinessConfiguration.all_tenants.filter(
            tenant_id=tenant.id, status="PUBLISHED",
            config_key__in=("pricing.actuarial_model", "pricing.reference_premiums", "pricing.formulas"),
        ).exists()
    )
    template = DocumentTemplateVersion.all_tenants.filter(
        tenant_id=tenant.id, status="PUBLISHED", document_type="QUOTE_PROPOSAL"
    ).exists()
    products = Product.all_tenants.filter(tenant_id=tenant.id).count()
    server_email_problems = [] if email_settings.effective_source(tenant.id) != "ENV" else email_config_problems()
    portal_on = bool(settings["limits"]["modules"].get("customerPortal", True))

    def step(key, label, done, detail, warning=False):
        return {"key": key, "label": label, "status": "DONE" if done else ("WARNING" if warning else "PENDING"),
                "detail": detail}

    steps = [
        step("company", "Dados da empresa", bool(profile.get("nif") and profile.get("email")),
             "NIF e email da seguradora registados." if profile.get("nif") and profile.get("email")
             else "Falta o NIF ou o email da seguradora na ficha."),
        step("firstAdmin", "Primeiro administrador", any(a.last_login_at for a in admins),
             "O administrador já entrou no Q360." if any(a.last_login_at for a in admins)
             else ("Administrador criado, mas ainda não entrou." if admins else "Ainda não há administrador."),
             warning=bool(admins)),
        step("products", "Produtos de mercado", products > 0,
             f"{products} produto(s) criado(s)." if products else "Ainda não há produtos."),
        step("tariff", "Tarifa publicada", tariff,
             "Há uma tarifa publicada." if tariff else "Sem tarifa publicada: as cotações não calculam o prémio."),
        step("proposalTemplate", "Modelo de proposta", template,
             "Modelo de proposta publicado." if template else "Usa o modelo padrão do Q360 (sem marca própria).",
             warning=True),
        step("email", "Email", not server_email_problems and bool(profile.get("email")),
             "Servidor de email configurado." if not server_email_problems
             else "Servidor de email por configurar: " + " ".join(server_email_problems),
             warning=not portal_on),
    ]
    missing = [s["label"] for s in steps if s["key"] in ("tariff", "proposalTemplate", "email") and s["status"] != "DONE"]
    return {
        "tenantId": str(tenant.id),
        "status": tenant.status,
        "lastLoginAt": last_login.isoformat() if last_login else None,
        "activeUsers": sum(1 for a in accounts if a.status == StaffAccount.ACTIVE),
        "maxUsers": settings["limits"].get("maxUsers"),
        "quotesThisMonth": Quote.all_tenants.filter(tenant_id=tenant.id, created_at__gte=month).count(),
        "policiesThisMonth": Policy.all_tenants.filter(tenant_id=tenant.id, created_at__gte=month).count(),
        "missingConfiguration": missing,
        "onboarding": {"steps": steps, "done": sum(1 for s in steps if s["status"] == "DONE"), "total": len(steps)},
        "suspension": settings.get("suspension"),
    }


@transaction.atomic
def add_tenant_admin(*, actor_id, tenant_id, email, name, correlation_id):
    tenant = _get(tenant_id)
    if StaffAccount.all_tenants.filter(email__iexact=email).exists():
        raise PlatformConflictError("O email já existe na plataforma")
    from apps.staff_accounts.application.account_service import ensure_user_limit

    ensure_user_limit(tenant.id)
    admin, password = _create_admin(tenant.id, email, name)
    credential_mail.send_welcome_email(
        to_email=admin.email, name=admin.name, password=password, tenant_name=tenant.name,
        account_id=str(admin.id), tenant_id=tenant.id,
    )
    record_platform_audit(
        actor_id=actor_id, action="platform.tenant_admin_added", entity_type="Tenant", entity_id=str(tenant.id),
        correlation_id=correlation_id, metadata={"adminId": str(admin.id), "adminEmail": admin.email},
    )
    return admin, password


@transaction.atomic
def reset_tenant_account_password(*, actor_id, tenant_id, account_id, correlation_id):
    tenant = _get(tenant_id)
    account = StaffAccount.all_tenants.filter(id=account_id, tenant_id=tenant.id).first()
    if account is None:
        raise PlatformNotFoundError("Conta não encontrada neste tenant")
    password = _temporary_password()
    StaffAccount.all_tenants.filter(id=account.id).update(
        password_hash=make_password(password), failed_login_attempts=0, locked_until=None
    )
    record_platform_audit(
        actor_id=actor_id, action="platform.tenant_account_password_reset", entity_type="StaffAccount",
        entity_id=str(account.id), correlation_id=correlation_id, metadata={"tenantId": str(tenant.id)},
        tenant_id=tenant.id,
    )
    credential_mail.send_password_reset_email(
        to_email=account.email, name=account.name, password=password, tenant_name=tenant.name,
        account_id=str(account.id), tenant_id=tenant.id,
    )
    return account, password


def record_tenant_access(*, actor_id, tenant_id, what: str, correlation_id=None) -> None:
    """Regista que um super administrador consultou dados de uma seguradora."""
    record_platform_audit(actor_id=actor_id, action="platform.tenant_viewed", entity_type="Tenant",
                          entity_id=str(tenant_id), correlation_id=correlation_id, metadata={"what": what})
