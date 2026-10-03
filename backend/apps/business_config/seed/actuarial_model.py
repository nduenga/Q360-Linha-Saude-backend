from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


WORKBOOK_PATH = Path(__file__).with_name("Modelo_Actuarial_Saude_SAU_SAG_Angola.xlsx")
AGE_GENDER_KEYS = ("M|0-17", "F|0-17", "M|18-35", "F|18-35", "M|36-50", "F|36-50", "M|51-65", "F|51-65", "M|>65", "F|>65")


def _value(cell: Any) -> Any:
    value = cell.value
    if isinstance(value, str) and value.startswith("="):
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _table(sheet, rows: range, columns: dict[str, int]) -> list[dict[str, Any]]:
    result = []
    for row_number in rows:
        row = {key: _value(sheet.cell(row_number, column)) for key, column in columns.items()}
        if any(value is not None for value in row.values()):
            result.append(row)
    return result


def build_actuarial_model() -> dict[str, Any]:
    workbook = load_workbook(WORKBOOK_PATH, data_only=False, read_only=True)
    dashboard = workbook["Dashboard_Premissas"]
    sau = workbook["Matriz_SAU"]
    sag = workbook["Matriz_SAG"]
    group_rules = workbook["Matriz_SAG"]
    adjustments = workbook["Regras_Ajustes"]

    coverage_assumptions = _table(
        dashboard,
        range(79, 96),
        {
            "name": 2, "code": 3, "group": 4, "frequency_unit": 5, "reference_cell": 6,
            "frequency_per_life": 7, "frequency_per_1000_lives": 8, "mean_network_cost_aoa": 9,
            "mean_reimbursement_cost_aoa": 10, "network_utilization": 11, "weighted_mean_cost_aoa": 12,
            "severity_cv": 13, "apply_network_factor": 14, "technical_rationale": 15,
        },
    )
    age_relativities = []
    for row_number in range(114, 131):
        code = _value(dashboard.cell(row_number, 3))
        if code is not None:
            age_relativities.append({
                "coverage_code": code,
                "factors": {key: _value(dashboard.cell(row_number, index)) for index, key in enumerate(AGE_GENDER_KEYS, start=4)},
            })

    plan_coverage_columns = {"plan": 2, "coverage_code": 3, "status": 6, "capital_sublimit_aoa": 7}
    plan_coverages = {
        "SAU": _table(sau, range(6, 57), plan_coverage_columns),
        "SAG": _table(sag, range(6, 57), plan_coverage_columns),
    }

    package_rows = _table(
        adjustments,
        range(49, 54),
        {
            "code": 2, "copayment_aoa": 3, "reimbursement_share": 4,
            "annual_outpatient_deductible_aoa": 5, "inpatient_deductible_aoa": 6,
            "reference_adjustment_sag": 9, "reference_adjustment_sau": 10,
        },
    )

    return {
        "model_status": "DRAFT_REQUIRES_ACTUARIAL_APPROVAL",
        "source_file": WORKBOOK_PATH.name,
        "source_sheets": ["Dashboard_Premissas", "Matriz_SAU", "Matriz_SAG", "Regras_Ajustes"],
        "currency_code": "AOA",
        "currency_label": "Kwanza (Kz)",
        "reference_date": _value(dashboard["D38"]),
        "approval_warning": _value(dashboard["A2"]),
        "assumptions": {
            "usd_to_aoa": _value(dashboard["D39"]),
            "general_inflation": _value(dashboard["D40"]),
            "medical_inflation_excess": _value(dashboard["D41"]),
            "imported_cost_fx_component": _value(dashboard["D42"]),
            "projection_months": _value(dashboard["D44"]),
            "loadings": {
                segment: {
                    "volatility": _value(dashboard.cell(50, column)),
                    "administration_expense": _value(dashboard.cell(51, column)),
                    "acquisition_commission": _value(dashboard.cell(52, column)),
                    "insurer_margin": _value(dashboard.cell(53, column)),
                    "stamp_duty": _value(dashboard.cell(55, column)),
                    "arseg_levy": _value(dashboard.cell(56, column)),
                }
                for segment, column in (("SAU", 4), ("SAG", 5))
            },
            "payment_installments": _table(
                dashboard, range(61, 65), {"frequency": 2, "installments": 3, "loading": 4}
            ),
            "age_exposure": _table(
                dashboard, range(69, 74),
                {"age_band": 2, "age_from": 3, "age_to": 4, "male_lives": 5, "female_lives": 6},
            ),
        },
        "coverage_assumptions": coverage_assumptions,
        "age_gender_relativities": age_relativities,
        "plan_coverages": plan_coverages,
        "plan_factors": _table(
            dashboard, range(154, 160),
            {"description": 2, "product_plan": 3, "network_factor": 4, "room_limit_per_day_aoa": 5, "icu_annual_limit_aoa": 6},
        ),
        "group_size_factors": _table(
            group_rules, range(100, 104),
            {"label": 2, "headcount_from": 3, "headcount_to": 4, "premium_adjustment": 5, "volatility": 6, "rationale": 7},
        ),
        "group_participation_factors": _table(
            group_rules, (106, 107, 109, 110, 111, 112),
            {"rule": 2, "minimum_participation": 3, "premium_adjustment": 4, "rationale": 5},
        ),
        "industry_factors": _table(
            group_rules, range(115, 122), {"industry": 2, "factor": 3, "rationale": 4}
        ),
        "adjustment_assumptions": {
            "copayment_per_visit_aoa": [_value(adjustments.cell(row, 2)) for row in range(24, 28)],
            "reimbursement_shares": [_value(adjustments.cell(row, 2)) for row in range(30, 34)],
            "outpatient_deductibles_aoa": [_value(adjustments.cell(row, 2)) for row in range(36, 40)],
            "inpatient_deductibles_aoa": [_value(adjustments.cell(row, 2)) for row in range(42, 46)],
            "participation_packages": package_rows,
            "pre_existing_severity": _table(
                adjustments, range(58, 63), {"severity": 2, "surcharge": 3, "decision": 4}
            ),
            "entry_age_adjustments": _table(
                adjustments, range(79, 84), {"age_from": 2, "surcharge": 3, "decision": 4}
            ),
            "family_size_discounts": _table(
                adjustments, range(88, 92), {"minimum_members": 2, "discount": 3}
            ),
            "cross_sell_discounts": _table(
                adjustments, range(94, 99), {"product": 2, "discount": 3}
            ),
            "no_claims_renewal_discount": _value(adjustments["C100"]),
            "maximum_cumulative_discount": _value(adjustments["C101"]),
            "regional_factors": _table(
                adjustments, range(104, 109), {"region": 2, "factor": 3, "rationale": 4}
            ),
            "copayment_demand_elasticity": _value(adjustments["C15"]),
            "reimbursement_behavioral_elasticity": _value(adjustments["C16"]),
            "annual_outpatient_utilization_probability": _value(adjustments["C18"]),
        },
    }