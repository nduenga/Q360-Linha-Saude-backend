"""Questionário clínico de cada pessoa segura: estrutura e validação.

As secções seguem o Manual visual v2 (cap. 10). As perguntas são um ponto de
partida e têm de ser validadas clinicamente antes de irem para produção; por
isso cada questionário guarda a versão com que foi preenchido.
"""
from __future__ import annotations

import datetime
from typing import Any

SCHEMA_VERSION = "2026-11-v1"
YES_NO = "YES_NO"
TEXT = "TEXT"
NUMBER = "NUMBER"
DATE = "DATE"


def _q(key: str, label: str, kind: str, *, required: bool = True, show_if: tuple[str, bool] | None = None) -> dict[str, Any]:
    question: dict[str, Any] = {"key": key, "label": label, "type": kind, "required": required}
    if show_if is not None:
        question["showIf"] = {"question": show_if[0], "equals": show_if[1]}
    return question


SECTIONS: list[dict[str, Any]] = [
    {"key": "identification", "label": "Identificação", "questions": [
        _q("heightCm", "Altura (cm)", NUMBER),
        _q("weightKg", "Peso (kg)", NUMBER),
    ]},
    {"key": "habits", "label": "Hábitos", "questions": [
        _q("smoker", "Fuma?", YES_NO),
        _q("regularAlcohol", "Consome bebidas alcoólicas com regularidade?", YES_NO),
    ]},
    {"key": "chronicConditions", "label": "Doenças crónicas", "questions": [
        _q("chronicCondition", "Tem alguma doença crónica diagnosticada?", YES_NO),
        _q("chronicConditionName", "Qual?", TEXT, show_if=("chronicCondition", True)),
        _q("chronicConditionSince", "Desde quando?", DATE, required=False, show_if=("chronicCondition", True)),
        _q("chronicConditionTreated", "Está em tratamento?", YES_NO, show_if=("chronicCondition", True)),
    ]},
    {"key": "hospitalisations", "label": "Internamentos", "questions": [
        _q("hospitalised", "Esteve internado nos últimos 5 anos?", YES_NO),
        _q("hospitalisationDetails", "Indique o motivo e a data", TEXT, show_if=("hospitalised", True)),
    ]},
    {"key": "medication", "label": "Medicação", "questions": [
        _q("regularMedication", "Toma medicação de forma regular?", YES_NO),
        _q("medicationDetails", "Indique qual", TEXT, show_if=("regularMedication", True)),
    ]},
]

_QUESTIONS = {question["key"]: question for section in SECTIONS for question in section["questions"]}
SECTION_KEYS = frozenset(section["key"] for section in SECTIONS)
DECLARATION_KEYS = ("chronicCondition", "hospitalised", "regularMedication")


class QuestionnaireAnswerError(ValueError):
    """Uma resposta não existe no questionário ou tem o tipo errado."""


def schema() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "sections": SECTIONS}


def _is_visible(question: dict[str, Any], answers: dict[str, Any]) -> bool:
    condition = question.get("showIf")
    return condition is None or answers.get(condition["question"]) == condition["equals"]


def _valid_value(question: dict[str, Any], value: Any) -> bool:
    kind = question["type"]
    if kind == YES_NO:
        return isinstance(value, bool)
    if kind == NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
    if kind == DATE:
        try:
            return isinstance(value, str) and datetime.date.fromisoformat(value) <= datetime.date.today()
        except ValueError:
            return False
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 2000


def validate_answers(answers: dict[str, Any]) -> dict[str, Any]:
    """Valida um preenchimento parcial. `None` limpa a resposta."""
    clean: dict[str, Any] = {}
    for key, value in answers.items():
        question = _QUESTIONS.get(key)
        if question is None:
            raise QuestionnaireAnswerError(f"A pergunta «{key}» não existe neste questionário.")
        if value is None:
            continue
        if not _valid_value(question, value):
            raise QuestionnaireAnswerError(f"A resposta a «{question['label']}» não é válida.")
        clean[key] = value.strip() if isinstance(value, str) else value
    return clean


def merge_answers(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Junta as respostas novas e retira as de perguntas que deixaram de se aplicar."""
    merged = {**current, **validate_answers(incoming)}
    for key, value in incoming.items():
        if value is None:
            merged.pop(key, None)
    return {
        key: value for key, value in merged.items() if _is_visible(_QUESTIONS[key], merged)
    }


def required_keys(answers: dict[str, Any]) -> list[str]:
    return [
        question["key"]
        for section in SECTIONS
        for question in section["questions"]
        if question["required"] and _is_visible(question, answers)
    ]


def progress(answers: dict[str, Any]) -> dict[str, int]:
    required = required_keys(answers)
    return {"answered": sum(1 for key in required if key in answers), "required": len(required)}


def missing_labels(answers: dict[str, Any]) -> list[str]:
    return [_QUESTIONS[key]["label"] for key in required_keys(answers) if key not in answers]


def has_declarations(answers: dict[str, Any]) -> bool:
    return any(answers.get(key) is True for key in DECLARATION_KEYS)
