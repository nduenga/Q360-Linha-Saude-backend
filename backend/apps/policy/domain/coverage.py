"""Coverage verification for the customer portal.

This module contains the business rules used to determine whether a
beneficiary is covered on a specific date.

The result must explain not only whether the beneficiary is covered,
but also why the beneficiary is not covered and, when applicable,
what document/action/decision is still pending.
"""

from __future__ import annotations

import dataclasses
import datetime


@dataclasses.dataclass(frozen=True, slots=True)
class PolicyFacts:
    status: str
    start_date: datetime.date | None
    end_date: datetime.date | None
    benefit_codes: frozenset[str]
    accident_waived_codes: frozenset[str] = frozenset()


@dataclasses.dataclass(frozen=True, slots=True)
class PolicyMemberFacts:
    # Estado do vínculo do beneficiário à apólice.
    # Ex.: ACTIVE, PENDING, REJECTED, EXCLUDED
    status: str

    # Estado global do beneficiário.
    # Ex.: ACTIVE, INACTIVE
    member_status: str | None

    # Motivo da pendência, quando existir.
    pending_reason_code: str | None

    # Data em que o beneficiário foi incluído na apólice.
    inclusion_date: datetime.date | None

    # Data em que o beneficiário deixou de estar incluído.
    exclusion_date: datetime.date | None

    # Fim dos períodos de carência por cobertura.
    waiting_period_ends: dict[str, datetime.date]


@dataclasses.dataclass(frozen=True, slots=True)
class CoverageResult:
    covered: bool
    reason_code: str
    message: str
    waiting_period_ends: datetime.date | None = None
    pending_reason_code: str | None = None
    required_action: str | None = None


_MESSAGES: dict[str, str] = {
    "POLICY_AWAITING_FIRST_PREMIUM":
        "A apólice ainda não está ativa — falta confirmar o pagamento da 1.ª fracção.",

    "POLICY_SUSPENDED_NO_PAYMENT":
        "A apólice está suspensa por falta de pagamento.",

    "POLICY_NOT_IN_FORCE":
        "A apólice não está em vigor nesta data.",

    "MEMBER_DEACTIVATED":
        "Este beneficiário está desativado.",

    "MEMBER_PENDING":
        "Este beneficiário ainda não está ativo — existe uma validação pendente.",

    "MEMBER_NOT_IN_FORCE":
        "Este beneficiário não está coberto nesta data.",

    "BENEFIT_NOT_IN_PLAN":
        "Esta cobertura não faz parte do plano contratado.",

    "IN_WAITING_PERIOD":
        "Ainda está em período de carência para esta cobertura.",

    "COVERED":
        "Coberto.",
}


# Código interno -> mensagem que explica exactamente o que falta.
_PENDING_ACTIONS: dict[str, str] = {
    "FALTA_CERTIFICADO_MATRICULA":
        "Falta enviar o certificado de matrícula válido do beneficiário.",

    "FALTA_HOMOLOGACAO_UNIAO_FACTO":
        "Falta enviar o documento de homologação da união de facto.",

    "FALTA_PROVA_DEPENDENCIA_ASCENDENTE":
        "Falta enviar o comprovativo de coabitação ou dependência financeira.",

    "PENDENTE_JUNTA_MEDICA":
        "Está pendente a decisão da Junta Médica da seguradora.",

    "ELIG-REFERRAL":
        "Está pendente a validação manual da seguradora.",
}


def _not_covered(
    reason_code: str,
    *,
    waiting_period_ends: datetime.date | None = None,
    pending_reason_code: str | None = None,
) -> CoverageResult:
    """Creates a non-covered result with an explicit explanation."""

    required_action = _PENDING_ACTIONS.get(pending_reason_code)

    message = _MESSAGES[reason_code]

    if reason_code == "MEMBER_PENDING":
        if required_action:
            message = (
                "Este beneficiário ainda não está ativo. "
                f"{required_action}"
            )
        else:
            message = (
                "Este beneficiário ainda não está ativo — "
                "a validação do beneficiário está pendente."
            )

    return CoverageResult(
        covered=False,
        reason_code=reason_code,
        message=message,
        waiting_period_ends=waiting_period_ends,
        pending_reason_code=pending_reason_code,
        required_action=required_action,
    )


_POLICY_TERMINAL_STATUSES = frozenset(
    {
        "TERMINATED",
        "CANCELLED",
        "EXPIRED",
        "RENEWED",
    }
)


# Estados do vínculo do beneficiário que não permitem cobertura.
_MEMBER_NOT_ACTIVE_STATUSES = frozenset(
    {
        "PENDING",
        "REJECTED",
        "EXCLUDED",
    }
)


def check_coverage(
    *,
    policy: PolicyFacts,
    member: PolicyMemberFacts | None,
    on_date: datetime.date,
    benefit_category: str | None,
    accident: bool = False,
) -> CoverageResult:

    # ---------------------------------------------------------
    # 1. Apólice aguarda primeiro pagamento
    # ---------------------------------------------------------
    if policy.status == "PENDING_FIRST_PREMIUM":
        return _not_covered(
            "POLICY_AWAITING_FIRST_PREMIUM"
        )

    # ---------------------------------------------------------
    # 2. Apólice suspensa
    # ---------------------------------------------------------
    if policy.status == "SUSPENDED":
        return _not_covered(
            "POLICY_SUSPENDED_NO_PAYMENT"
        )

    # ---------------------------------------------------------
    # 3. Apólice fora de vigor
    # ---------------------------------------------------------
    if policy.status in _POLICY_TERMINAL_STATUSES:
        return _not_covered(
            "POLICY_NOT_IN_FORCE"
        )

    if policy.status != "ACTIVE":
        return _not_covered(
            "POLICY_NOT_IN_FORCE"
        )

    if (
        policy.start_date is None
        or policy.end_date is None
        or not (
            policy.start_date <= on_date <= policy.end_date
        )
    ):
        return _not_covered(
            "POLICY_NOT_IN_FORCE"
        )

    # ---------------------------------------------------------
    # 4. Beneficiário inexistente
    # ---------------------------------------------------------
    if member is None:
        return _not_covered(
            "MEMBER_NOT_IN_FORCE"
        )

    # ---------------------------------------------------------
    # 5. Beneficiário DESACTIVADO
    #
    # Esta é a correcção principal.
    #
    # InsuredMember.status = INACTIVE
    # significa que o beneficiário foi desactivado.
    # ---------------------------------------------------------
    if member.member_status == "INACTIVE":
        return _not_covered(
            "MEMBER_DEACTIVATED"
        )

    # ---------------------------------------------------------
    # 6. Beneficiário pendente/rejeitado/excluído
    # ---------------------------------------------------------
    if member.status in _MEMBER_NOT_ACTIVE_STATUSES:
        return _not_covered(
            "MEMBER_PENDING",
            pending_reason_code=member.pending_reason_code,
        )

    # ---------------------------------------------------------
    # 7. Data de inclusão
    # ---------------------------------------------------------
    if (
        member.inclusion_date is None
        or on_date < member.inclusion_date
    ):
        return _not_covered(
            "MEMBER_NOT_IN_FORCE"
        )

    # ---------------------------------------------------------
    # 8. Data de exclusão
    # ---------------------------------------------------------
    if (
        member.exclusion_date is not None
        and on_date >= member.exclusion_date
    ):
        return _not_covered(
            "MEMBER_NOT_IN_FORCE"
        )

    # ---------------------------------------------------------
    # 9. Cobertura pertence ao plano?
    # ---------------------------------------------------------
    if (
        benefit_category is not None
        and benefit_category not in policy.benefit_codes
    ):
        return _not_covered(
            "BENEFIT_NOT_IN_PLAN"
        )

    # ---------------------------------------------------------
    # 10. Período de carência
    # ---------------------------------------------------------
    if (
        benefit_category is not None
        and not (
            accident
            and benefit_category in policy.accident_waived_codes
        )
    ):
        ends = member.waiting_period_ends.get(
            benefit_category
        )

        if ends is not None and on_date < ends:
            return _not_covered(
                "IN_WAITING_PERIOD",
                waiting_period_ends=ends,
            )

    # ---------------------------------------------------------
    # 11. Está coberto
    # ---------------------------------------------------------
    return CoverageResult(
        covered=True,
        reason_code="COVERED",
        message=_MESSAGES["COVERED"],
    )