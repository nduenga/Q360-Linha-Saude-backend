"""Definições de plano (`plan.settings_json`) — regras do PDF "Seguro de Saúde —
Coberturas e Capitais" (1-Out-2026) que descrevem **como o plano se comporta**
e não uma cobertura em particular.

Tudo aqui é configuração editável pelo GTE (requisito R7): idades, regras de
grupo, opções de participação A–E, tratamento de doenças preexistentes... Os
valores numéricos do PDF são indicativos e só aparecem nos modelos
(`market_templates.py`), nunca como constantes de decisão neste validador.

Duas saídas, de propósito:
  - **erros** (`InvalidPlanSettingsError`): contradizem uma regra do PDF
    ou estão mal formados — a gravação é recusada;
  - **avisos** (`warnings`): situações que o PDF recomenda tratar
    ("verificar a cobertura geográfica...") mas que o GTE pode decidir
    conscientemente — a gravação passa e o aviso é devolvido ao front.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.foundation.domain.problem import DomainProblem

SEGMENTS = ("INDIVIDUAL_FAMILY", "GROUP")
TIERS = ("BASE", "MEDIUM", "SUPERIOR", "CUSTOM")
ACCESS_SYSTEMS = ("NETWORK", "REIMBURSEMENT", "MIXED")
PARTICIPATION_CODES = ("A", "B", "C", "D", "E")
PRE_EXISTING_MODES = (
    "TOTAL_EXCLUSION",  # Exclusão total — Individual, padrão
    "SPECIFIC_EXCLUSION",  # Exclusão específica — Individual, após análise médica
    "ACCEPTED_WITH_WAITING",  # Aceitação com carência (12 a 24 meses) — Individual Superior
    "ACCEPTED_WITH_LOADING",  # Aceitação com sobreprémio — Individual, casos selecionados
    "ACCEPTED_WITH_SUBLIMIT",  # Aceitação com sublimite — Grupo e Individual
    "FULL_ACCEPTANCE",  # Aceitação integral — Grupo com adesão obrigatória
)
PREMIUM_BASES = ("FIXED_PER_PERSON", "PER_AGE_BAND", "EXPERIENCE")
ADHESIONS = ("MANDATORY", "OPTIONAL")
PREMIUM_PAYERS = ("COMPANY", "EMPLOYEE_COPAYS_FAMILY")
NETWORK_REGIONS = ("LUANDA", "PROVINCES")

_ALLOWED_KEYS = {
    "segment", "tier", "category", "accessSystem", "participationOption", "participationOptions",
    "entryAge", "permanenceAge", "household", "clinicalQuestionnaire", "group", "preExistingTreatment",
    "waitingRules", "network", "priorAuthorization", "capitalIndexation", "currency", "noProRata", "notes",
    "indicative", "source",
}


class InvalidPlanSettingsError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def decimal_value(raw: Any, path: str, *, minimum: Decimal | None = Decimal("0"), maximum: Decimal | None = None) -> Decimal:
    """Money/percentages travel as decimal strings (ART-006 rule used
    everywhere in this API)."""
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        raise InvalidPlanSettingsError(f"{path} must be a decimal serialised as a string")
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise InvalidPlanSettingsError(f"{path} is not a valid decimal") from exc
    if not value.is_finite():
        raise InvalidPlanSettingsError(f"{path} is not a finite decimal")
    if minimum is not None and value < minimum:
        raise InvalidPlanSettingsError(f"{path} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise InvalidPlanSettingsError(f"{path} must be <= {maximum}")
    return value


def _obj(raw: Any, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise InvalidPlanSettingsError(f"{path} must be an object")
    return raw


def _int(raw: Any, path: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise InvalidPlanSettingsError(f"{path} must be an integer")
    if raw < minimum or (maximum is not None and raw > maximum):
        raise InvalidPlanSettingsError(f"{path} must be between {minimum} and {maximum if maximum is not None else '∞'}")
    return raw


def _bool(raw: Any, path: str) -> bool:
    if not isinstance(raw, bool):
        raise InvalidPlanSettingsError(f"{path} must be a boolean")
    return raw


def _choice(raw: Any, path: str, choices: tuple[str, ...]) -> str:
    if raw not in choices:
        raise InvalidPlanSettingsError(f"{path} must be one of {list(choices)}")
    return raw


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def validate_plan_settings(raw: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Returns `(settings, warnings)`; raises `InvalidPlanSettingsError`."""
    settings = _obj(raw if raw is not None else {}, "settings")
    warnings: list[dict[str, str]] = []
    if not settings:
        return {}, warnings

    unknown = set(settings) - _ALLOWED_KEYS
    if unknown:
        raise InvalidPlanSettingsError(f"Unknown plan setting(s): {sorted(unknown)}")

    segment = _choice(settings.get("segment"), "settings.segment", SEGMENTS)
    if "tier" in settings and settings["tier"] is not None:
        _choice(settings["tier"], "settings.tier", TIERS)
    if "accessSystem" in settings:
        _choice(settings["accessSystem"], "settings.accessSystem", ACCESS_SYSTEMS)
    if "currency" in settings:
        _choice(settings["currency"], "settings.currency", ("AOA", "USD"))
    if settings.get("noProRata") is False:
        raise InvalidPlanSettingsError(
            "settings.noProRata cannot be false: in health insurance there is no pro-rata rule — once the annual "
            "capital is exhausted the insurer stops paying until the next anniversary"
        )

    # ---- idades (PDF: entrada até 60–65, renovação até 70–75; tarifar por escalão etário)
    entry_age = permanence_age = None
    if "entryAge" in settings:
        entry = _obj(settings["entryAge"], "settings.entryAge")
        entry_age = (_int(entry.get("min", 0), "settings.entryAge.min", maximum=120), _int(entry.get("max"), "settings.entryAge.max", maximum=120))
        if entry_age[0] > entry_age[1]:
            raise InvalidPlanSettingsError("settings.entryAge.min cannot exceed settings.entryAge.max")
    if "permanenceAge" in settings:
        permanence = _obj(settings["permanenceAge"], "settings.permanenceAge")
        permanence_age = _int(permanence.get("max"), "settings.permanenceAge.max", maximum=120)
    if entry_age and permanence_age is not None and entry_age[1] > permanence_age:
        raise InvalidPlanSettingsError("settings.permanenceAge.max cannot be lower than settings.entryAge.max")
    if segment == "INDIVIDUAL_FAMILY" and (entry_age is None or permanence_age is None):
        warnings.append(
            _warning(
                "AGE_LIMITS_MISSING",
                "Fixar limites de idade de entrada e de permanência (PDF: entrada até 60–65 anos, "
                "renovação até 70–75) — o prémio é tarifado por escalão etário.",
            )
        )

    # ---- agregado familiar (só Individual/Familiar)
    if "household" in settings:
        if segment != "INDIVIDUAL_FAMILY":
            raise InvalidPlanSettingsError("settings.household only applies to INDIVIDUAL_FAMILY plans")
        household = _obj(settings["household"], "settings.household")
        if "spouse" in household:
            _bool(household["spouse"], "settings.household.spouse")
        if "dependentChildMaxAge" in household:
            _int(household["dependentChildMaxAge"], "settings.household.dependentChildMaxAge", minimum=1, maximum=30)
        if "studentsOnlyAboveAge" in household:
            _int(household["studentsOnlyAboveAge"], "settings.household.studentsOnlyAboveAge", minimum=1, maximum=30)

    # ---- questionário clínico
    if "clinicalQuestionnaire" in settings:
        questionnaire = _obj(settings["clinicalQuestionnaire"], "settings.clinicalQuestionnaire")
        if "required" in questionnaire:
            required = _bool(questionnaire["required"], "settings.clinicalQuestionnaire.required")
            if segment == "INDIVIDUAL_FAMILY" and not required:
                raise InvalidPlanSettingsError(
                    "settings.clinicalQuestionnaire.required cannot be false on an INDIVIDUAL_FAMILY plan: "
                    "the clinical questionnaire is mandatory in individual health insurance"
                )
        if "medicalExamAboveAge" in questionnaire:
            _int(questionnaire["medicalExamAboveAge"], "settings.clinicalQuestionnaire.medicalExamAboveAge", maximum=120)
        if questionnaire.get("medicalExamAboveCapital") is not None:
            decimal_value(
                questionnaire["medicalExamAboveCapital"], "settings.clinicalQuestionnaire.medicalExamAboveCapital"
            )

    # ---- grupo
    group_adhesion = None
    if "group" in settings:
        if segment != "GROUP":
            raise InvalidPlanSettingsError("settings.group only applies to GROUP plans")
        group = _obj(settings["group"], "settings.group")
        if "minInsured" in group:
            minimum = _int(group["minInsured"], "settings.group.minInsured", minimum=1)
            if not 5 <= minimum <= 10:
                warnings.append(
                    _warning(
                        "GROUP_MIN_SIZE_ATYPICAL",
                        "Dimensão mínima típica do grupo: 5 a 10 pessoas seguras (abaixo disso, produto individual).",
                    )
                )
        if "adhesion" in group:
            group_adhesion = _choice(group["adhesion"], "settings.group.adhesion", ADHESIONS)
        if "questionnaireWaivedAboveInsured" in group:
            _int(group["questionnaireWaivedAboveInsured"], "settings.group.questionnaireWaivedAboveInsured", minimum=1)
        if "premiumBasis" in group:
            _choice(group["premiumBasis"], "settings.group.premiumBasis", PREMIUM_BASES)
        if "premiumPayer" in group:
            _choice(group["premiumPayer"], "settings.group.premiumPayer", PREMIUM_PAYERS)
        if "categories" in group:
            categories = group["categories"]
            if not isinstance(categories, list) or not 1 <= len(categories) <= 3:
                warnings.append(_warning("GROUP_CATEGORIES", "Plano único, ou 2–3 planos por categoria profissional."))
        for flag in (
            "includesRetirees", "familyExtension", "continuityAfterLeaving", "monthlyInclusionsExclusions",
            "annualPremiumAdjustment",
        ):
            if flag in group:
                _bool(group[flag], f"settings.group.{flag}")
        if "profitSharing" in group and group["profitSharing"] is not None:
            sharing = _obj(group["profitSharing"], "settings.group.profitSharing")
            decimal_value(
                sharing.get("lossRatioThresholdPct"), "settings.group.profitSharing.lossRatioThresholdPct",
                minimum=Decimal("0.01"), maximum=Decimal("99.99"),
            )
            if sharing.get("refundPct") is not None:
                decimal_value(sharing["refundPct"], "settings.group.profitSharing.refundPct", maximum=Decimal("100"))
    elif segment == "GROUP":
        warnings.append(_warning("GROUP_SETTINGS_MISSING", "Plano de Grupo sem regras de grupo (dimensão mínima, adesão, prémio)."))

    # ---- opções de participação A–E
    options = settings.get("participationOptions")
    option_codes: list[str] = []
    if options is not None:
        if not isinstance(options, list) or not options:
            raise InvalidPlanSettingsError("settings.participationOptions must be a non-empty list")
        parsed: dict[str, dict[str, Any]] = {}
        for idx, option in enumerate(options):
            option = _obj(option, f"settings.participationOptions[{idx}]")
            code = _choice(option.get("code"), f"settings.participationOptions[{idx}].code", PARTICIPATION_CODES)
            if code in parsed:
                raise InvalidPlanSettingsError(f"settings.participationOptions has duplicate option '{code}'")
            entry: dict[str, Any] = {"code": code}
            for field in ("annualDeductible", "copayPerConsultation", "perEventDeductible"):
                if option.get(field) is not None:
                    entry[field] = decimal_value(option[field], f"settings.participationOptions[{idx}].{field}")
            if option.get("reimbursementPct") is not None:
                entry["reimbursementPct"] = decimal_value(
                    option["reimbursementPct"], f"settings.participationOptions[{idx}].reimbursementPct", maximum=Decimal("100")
                )
            entry["premiumAdjustmentPct"] = decimal_value(
                option.get("premiumAdjustmentPct"),
                f"settings.participationOptions[{idx}].premiumAdjustmentPct",
                minimum=Decimal("-99.99"),
                maximum=Decimal("1000"),
            )
            entry["hospitalOnly"] = bool(option.get("hospitalOnly", False))
            parsed[code] = entry
        option_codes = [c for c in PARTICIPATION_CODES if c in parsed]
        _validate_participation_monotonic([parsed[c] for c in option_codes])
    if settings.get("participationOption") is not None:
        selected = _choice(settings["participationOption"], "settings.participationOption", PARTICIPATION_CODES)
        if options is None or selected not in option_codes:
            raise InvalidPlanSettingsError(
                f"settings.participationOption '{selected}' must be defined in settings.participationOptions"
            )

    # ---- doenças preexistentes (6 tratamentos do PDF)
    if "preExistingTreatment" in settings and settings["preExistingTreatment"] is not None:
        treatment = _obj(settings["preExistingTreatment"], "settings.preExistingTreatment")
        mode = _choice(treatment.get("mode"), "settings.preExistingTreatment.mode", PRE_EXISTING_MODES)
        if mode == "FULL_ACCEPTANCE":
            if segment != "GROUP" or group_adhesion != "MANDATORY":
                raise InvalidPlanSettingsError(
                    "FULL_ACCEPTANCE of pre-existing conditions only applies to GROUP plans with MANDATORY adhesion"
                )
        if mode == "ACCEPTED_WITH_WAITING":
            _int(treatment.get("waitingMonths"), "settings.preExistingTreatment.waitingMonths", minimum=12, maximum=24)
            if settings.get("tier") != "SUPERIOR" and segment == "INDIVIDUAL_FAMILY":
                warnings.append(
                    _warning("PRE_EXISTING_WAITING_TIER", "Aceitação com carência (12 a 24 meses) aplica-se tipicamente ao Individual Superior.")
                )
        if mode == "ACCEPTED_WITH_LOADING":
            decimal_value(
                treatment.get("loadingPct"), "settings.preExistingTreatment.loadingPct", minimum=Decimal("0.01"), maximum=Decimal("1000")
            )
        if mode == "ACCEPTED_WITH_SUBLIMIT":
            decimal_value(
                treatment.get("sublimitAmount"), "settings.preExistingTreatment.sublimitAmount", minimum=Decimal("0.01")
            )

    # ---- carências, rede, pré-autorização, indexação
    if "waitingRules" in settings:
        rules = _obj(settings["waitingRules"], "settings.waitingRules")
        for flag in ("accidentWaived", "groupMandatoryEliminatesWaiting"):
            if flag in rules:
                _bool(rules[flag], f"settings.waitingRules.{flag}")
        if rules.get("accidentWaived") is False:
            warnings.append(_warning("ACCIDENT_WAITING", "Em acidente, as carências não se aplicam na generalidade dos produtos."))
    access = settings.get("accessSystem")
    if "network" in settings:
        network = _obj(settings["network"], "settings.network")
        regions = network.get("regions", [])
        if not isinstance(regions, list) or not set(regions) <= set(NETWORK_REGIONS):
            raise InvalidPlanSettingsError(f"settings.network.regions must be a list within {list(NETWORK_REGIONS)}")
        if access in ("NETWORK", "MIXED") and not regions:
            warnings.append(
                _warning("NETWORK_COVERAGE", "Verificar a cobertura geográfica da rede (Luanda vs províncias) e as tabelas de preços acordadas.")
            )
    elif access in ("NETWORK", "MIXED"):
        warnings.append(
            _warning("NETWORK_COVERAGE", "Verificar a cobertura geográfica da rede (Luanda vs províncias) e as tabelas de preços acordadas.")
        )
    if "priorAuthorization" in settings:
        prior = _obj(settings["priorAuthorization"], "settings.priorAuthorization")
        for flag in ("internments", "highCostExams", "scheduledSurgeries"):
            if flag in prior:
                _bool(prior[flag], f"settings.priorAuthorization.{flag}")
    if "capitalIndexation" in settings:
        indexation = _obj(settings["capitalIndexation"], "settings.capitalIndexation")
        if indexation.get("medicalInflationPct") is not None:
            decimal_value(indexation["medicalInflationPct"], "settings.capitalIndexation.medicalInflationPct", maximum=Decimal("1000"))
        if "reviewOnRenewal" in indexation:
            _bool(indexation["reviewOnRenewal"], "settings.capitalIndexation.reviewOnRenewal")

    normalised = dict(settings)
    normalised["noProRata"] = True
    return normalised, warnings


def _validate_participation_monotonic(options: list[dict[str, Any]]) -> None:
    """PDF: "Quanto maior a participação escolhida, menor o prémio."
    Options A→D are ordered by increasing participation: premium adjustment
    must strictly decrease, deductibles/copayments never decrease and the
    reimbursement share never increases. Option E ("só hospitalização")
    removes outpatient cover altogether, so it only has to be the cheapest."""
    ordered = [o for o in options if o["code"] != "E"] + [o for o in options if o["code"] == "E"]
    previous: dict[str, Any] | None = None
    for option in ordered:
        if previous is not None:
            if option["premiumAdjustmentPct"] >= previous["premiumAdjustmentPct"]:
                raise InvalidPlanSettingsError(
                    f"participation option {option['code']} must have a lower premium adjustment than "
                    f"{previous['code']} (the higher the participation, the lower the premium)"
                )
            if option["code"] != "E":
                for field in ("annualDeductible", "copayPerConsultation"):
                    if field in option and field in previous and option[field] < previous[field]:
                        raise InvalidPlanSettingsError(
                            f"participation option {option['code']} cannot have a lower {field} than {previous['code']}"
                        )
                if "reimbursementPct" in option and "reimbursementPct" in previous and option["reimbursementPct"] > previous["reimbursementPct"]:
                    raise InvalidPlanSettingsError(
                        f"participation option {option['code']} cannot reimburse a higher share than {previous['code']}"
                    )
        previous = option

