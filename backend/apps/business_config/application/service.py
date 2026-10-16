"""Ciclo de vida da configuração de negócio: DRAFT -> PENDING_APPROVAL ->
PUBLISHED -> RETIRED, com PENDING_APPROVAL -> REJECTED (motivo obrigatório);
uma versão REJECTED volta a DRAFT ao ser editada ou é reenviada para
aprovação. O criador nunca aprova nem rejeita a própria versão (four-eyes)."""
import hashlib
import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.business_config.application import role_permissions
from apps.business_config.application.platform_limits import check_platform_limits
from apps.business_config.application.readers import BusinessSnapshot
from apps.business_config.domain.catalog import CATALOG_BY_KEY
from apps.business_config.domain.product_setup import is_product_setup_key, validate_product_setup
from apps.business_config.domain.errors import (
    ConfigurationStateError,
    ConfigurationVersionConflict,
    FourEyesViolation,
    InvalidConfiguration,
    RoleNotAllowed,
)
from apps.business_config.domain.validators import validate_for_publication, validate_structure
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.infrastructure.models import AuditEvent


# Estados em que o autor ainda pode alterar e (re)submeter a versão.
EDITABLE_STATUSES = ("DRAFT", "REJECTED")


def tid():
    return CurrentTenantProvider.require().value


def actor_id(request=None):
    actor = CurrentActorProvider.get()
    return str(getattr(actor, "actor_id", None) or getattr(actor, "subject", None) or "system")


def digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def audit(action, c, extra=None):
    AuditEvent.all_tenants.create(
        tenant_id=tid(), actor_id=actor_id(), actor_type="USER", action=action,
        entity_type="BUSINESS_CONFIGURATION", entity_id=str(c.id), source="business-config",
        metadata_json={"configKey": c.config_key, "version": c.version_no, "status": c.status,
                       "checksum": c.checksum, **(extra or {})},
    )


def validate(key, value, effective_from=None, effective_to=None):
    product_setup = is_product_setup_key(key)
    if key not in CATALOG_BY_KEY and not product_setup:
        raise InvalidConfiguration("Configuração não suportada.")
    if not isinstance(value, dict):
        raise InvalidConfiguration("A configuração deve ser um objeto.")
    if effective_from and effective_to and effective_to < effective_from:
        raise InvalidConfiguration("effectiveTo não pode ser anterior a effectiveFrom.")
    if product_setup:
        # Grupos de opções, campos, valores e fórmulas de um produto.
        validate_product_setup(value)
        return
    validate_structure(key, value)


def _rules() -> dict:
    return BusinessSnapshot.load().get("security.approval_rules") or {}


def _require_role(field: str) -> None:
    """`security.approval_rules`: perfis que editam/aprovam. ADMIN pode sempre
    (evita bloquear a configuração)."""
    allowed = set(_rules().get(field) or [])
    actor = CurrentActorProvider.get()
    roles = {r.value for r in (actor.roles if actor else ())}
    if allowed and "ADMIN" not in roles and not roles & allowed:
        raise RoleNotAllowed(f"O seu perfil não tem permissão para esta operação (perfis permitidos: {sorted(allowed | {'ADMIN'})}).")


@transaction.atomic
def create_configuration(request, config_key, value, effective_from, effective_to=None, metadata=None):
    _require_role("editable_roles")
    validate(config_key, value, effective_from, effective_to)
    last = (BusinessConfiguration.objects.select_for_update()
            .filter(config_key=config_key).order_by("-version_no").first())
    c = BusinessConfiguration.all_tenants.create(
        tenant_id=tid(), config_key=config_key, version_no=(last.version_no + 1 if last else 1),
        effective_from=effective_from, effective_to=effective_to, status="DRAFT",
        value_json=value, metadata_json=metadata or {}, checksum=digest(value), created_by=actor_id(),
    )
    audit("BUSINESS_CONFIGURATION_CREATED", c)
    return c


@transaction.atomic
def update_configuration(request, c, value, effective_from=None, effective_to=None, metadata=None, row_version=None):
    _require_role("editable_roles")
    if c.status not in EDITABLE_STATUSES:
        raise ConfigurationStateError("Apenas DRAFT ou REJECTED pode ser editado.")
    if row_version is not None and c.row_version != row_version:
        raise ConfigurationVersionConflict("Conflito de versão: a configuração foi alterada por outro utilizador.")
    validate(c.config_key, value, effective_from or c.effective_from, effective_to or c.effective_to)
    c.value_json = value
    if effective_from is not None:
        c.effective_from = effective_from
    if effective_to is not None:
        c.effective_to = effective_to
    if metadata is not None:
        c.metadata_json = metadata
    c.checksum = digest(value)
    c.status = "DRAFT"  # uma versão REJECTED corrigida volta a rascunho
    c.row_version += 1
    c.save()
    audit("BUSINESS_CONFIGURATION_UPDATED", c)
    return c


@transaction.atomic
def submit_configuration(request, c, change_reason=None):
    if c.status not in EDITABLE_STATUSES:
        raise ConfigurationStateError("Apenas DRAFT ou REJECTED pode ser enviado para aprovação.")
    _require_role("editable_roles")
    if is_product_setup_key(c.config_key):
        validate_product_setup(c.value_json)
    else:
        validate_structure(c.config_key, c.value_json)
    validate_for_publication(c.config_key, c.value_json)
    check_platform_limits(c.config_key, c.value_json)
    c.status = "PENDING_APPROVAL"
    c.submitted_at = timezone.now()
    c.row_version += 1
    c.save()
    audit("BUSINESS_CONFIGURATION_SUBMITTED", c,
          extra={"reason": change_reason.strip()[:1000]} if change_reason and change_reason.strip() else None)
    return c


@transaction.atomic
def approve_configuration(request, c):
    if c.status != "PENDING_APPROVAL":
        raise ConfigurationStateError("Apenas PENDING_APPROVAL pode ser aprovado.")
    _require_role("approval_roles")
    who = actor_id()
    if c.created_by == who and _rules().get("four_eyes_required") is not False:
        raise FourEyesViolation("O criador não pode aprovar a própria configuração.")
    # Os tetos do fornecedor podem ter mudado desde a submissão.
    check_platform_limits(c.config_key, c.value_json)
    now = timezone.now()
    # A nova versão substitui a anterior vigente da mesma chave.
    for old in (BusinessConfiguration.objects.select_for_update()
                .filter(config_key=c.config_key, status="PUBLISHED").exclude(id=c.id)):
        if old.effective_from >= c.effective_from:
            continue
        if old.effective_to is None or old.effective_to >= c.effective_from:
            old.effective_to = c.effective_from - timedelta(days=1)
            old.save()
    c.status = "PUBLISHED"
    c.approved_by = who
    c.published_by = who
    c.approved_at = now
    c.published_at = now
    c.row_version += 1
    c.save()
    role_permissions.invalidate(tid())
    audit("BUSINESS_CONFIGURATION_PUBLISHED", c)
    return c


@transaction.atomic
def reject_configuration(request, c, reason):
    """O aprovador devolve a versão ao autor: fica REJECTED, com o motivo nos
    metadados (`lastRejection` + `rejections`) e na auditoria."""
    if c.status != "PENDING_APPROVAL":
        raise ConfigurationStateError("Apenas PENDING_APPROVAL pode ser rejeitado.")
    _require_role("approval_roles")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise InvalidConfiguration("Indique o motivo da rejeição (pelo menos 5 caracteres).")
    who = actor_id()
    if c.created_by == who and _rules().get("four_eyes_required") is not False:
        raise FourEyesViolation("O criador não pode decidir sobre a própria configuração.")
    rejection = {"reason": reason[:1000], "rejectedBy": who, "rejectedAt": timezone.now().isoformat()}
    metadata = dict(c.metadata_json or {})
    metadata["lastRejection"] = rejection
    metadata["rejections"] = [*(metadata.get("rejections") or []), rejection]
    c.metadata_json = metadata
    c.status = "REJECTED"
    c.submitted_at = None
    c.row_version += 1
    c.save()
    audit("BUSINESS_CONFIGURATION_REJECTED", c, extra={"reason": rejection["reason"]})
    return c


def configuration_history(c):
    """Eventos de auditoria de uma versão (criação, edições, submissão,
    rejeições, publicação, retirada), do mais antigo para o mais recente."""
    events = (AuditEvent.all_tenants.filter(tenant_id=c.tenant_id, entity_type="BUSINESS_CONFIGURATION",
                                            entity_id=str(c.id)).order_by("occurred_at"))
    return [
        {
            "action": e.action,
            "actorId": e.actor_id,
            "occurredAt": e.occurred_at.isoformat() if e.occurred_at else None,
            "status": (e.metadata_json or {}).get("status"),
            "checksum": (e.metadata_json or {}).get("checksum"),
            "reason": (e.metadata_json or {}).get("reason"),
        }
        for e in events
    ]


@transaction.atomic
def retire_configuration(request, c):
    if c.status != "PUBLISHED":
        raise ConfigurationStateError("Apenas PUBLISHED pode ser retirado.")
    _require_role("editable_roles")
    c.status = "RETIRED"
    c.row_version += 1
    c.save()
    role_permissions.invalidate(tid())
    audit("BUSINESS_CONFIGURATION_RETIRED", c)
    return c


def _diff(old, new, path=""):
    """Diferenças entre dois valores JSON: lista de {path, change, before, after}."""
    if isinstance(old, dict) and isinstance(new, dict):
        changes = []
        for key in sorted(set(old) | set(new), key=str):
            child = f"{path}.{key}" if path else str(key)
            if key not in old:
                changes.append({"path": child, "change": "ADDED", "before": None, "after": new[key]})
            elif key not in new:
                changes.append({"path": child, "change": "REMOVED", "before": old[key], "after": None})
            else:
                changes.extend(_diff(old[key], new[key], child))
        return changes
    if isinstance(old, list) and isinstance(new, list):
        changes = []
        for index in range(max(len(old), len(new))):
            child = f"{path}[{index}]"
            if index >= len(old):
                changes.append({"path": child, "change": "ADDED", "before": None, "after": new[index]})
            elif index >= len(new):
                changes.append({"path": child, "change": "REMOVED", "before": old[index], "after": None})
            else:
                changes.extend(_diff(old[index], new[index], child))
        return changes
    return [] if old == new else [{"path": path, "change": "CHANGED", "before": old, "after": new}]


def diff_values(old, new) -> list[dict]:
    """Diferenças entre dois valores de configuração (ver `_diff`)."""
    return _diff(old, new)


def compare_configurations(base, other):
    if base.config_key != other.config_key:
        raise InvalidConfiguration("Só é possível comparar versões da mesma configuração (configKey).")
    return {
        "configKey": base.config_key,
        "base": {"id": str(base.id), "version": base.version_no, "status": base.status, "checksum": base.checksum},
        "other": {"id": str(other.id), "version": other.version_no, "status": other.status, "checksum": other.checksum},
        "changes": _diff(base.value_json, other.value_json),
    }

