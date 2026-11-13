"""Questionário clínico de cada pessoa segura: estrutura e validação.

As secções seguem o Manual visual v2 (cap. 10). As perguntas são um ponto de
partida e têm de ser validadas clinicamente antes de irem para produção; por
isso cada questionário guarda a versão com que foi preenchido.
"""
from __future__ import annotations

import datetime
from copy import deepcopy
from typing import Any

SCHEMA_VERSION = "2026-11-v1"
YES_NO = "YES_NO"
TEXT = "TEXT"
NUMBER = "NUMBER"
DATE = "DATE"
SELECT = "SELECT"
MULTI_SELECT = "MULTI_SELECT"
ALLOWED_TYPES = frozenset((YES_NO, TEXT, NUMBER, DATE, SELECT, MULTI_SELECT))


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


class QuestionnaireSchemaError(ValueError):
    """A definição criada na Administração não é um questionário válido."""


def validate_schema(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("sections"), list) or not value["sections"]:
        raise QuestionnaireSchemaError("O questionário deve conter pelo menos uma secção.")
    version = value.get("version")
    if not isinstance(version, str) or not version.strip() or len(version) > 30:
        raise QuestionnaireSchemaError("Indique uma versão do questionário (até 30 caracteres).")
    section_keys, questions = set(), {}
    for section in value["sections"]:
        if not isinstance(section, dict): raise QuestionnaireSchemaError("Cada secção deve ser um objeto.")
        key, label, rows = section.get("key"), section.get("label"), section.get("questions")
        if not isinstance(key, str) or not key.strip() or key in section_keys: raise QuestionnaireSchemaError("Cada secção precisa de uma chave única.")
        if not isinstance(label, str) or not label.strip() or not isinstance(rows, list) or not rows: raise QuestionnaireSchemaError(f"A secção {key!r} precisa de título e pelo menos uma pergunta.")
        section_keys.add(key)
        for question in rows:
            if not isinstance(question, dict): raise QuestionnaireSchemaError("Cada pergunta deve ser um objeto.")
            qkey, qlabel, kind = question.get("key"), question.get("label"), question.get("type")
            if not isinstance(qkey, str) or not qkey.strip() or qkey in questions: raise QuestionnaireSchemaError("Cada pergunta precisa de uma chave única.")
            if not isinstance(qlabel, str) or not qlabel.strip() or kind not in ALLOWED_TYPES: raise QuestionnaireSchemaError(f"A pergunta {qkey!r} tem texto ou tipo inválido.")
            if not isinstance(question.get("required", True), bool): raise QuestionnaireSchemaError(f"required de {qkey!r} deve ser verdadeiro/falso.")
            options = question.get("options")
            if kind in (SELECT, MULTI_SELECT) and (not isinstance(options, list) or not options or not all(isinstance(x, str) and x.strip() for x in options) or len(set(options)) != len(options)): raise QuestionnaireSchemaError(f"A pergunta {qkey!r} precisa de opções únicas.")
            if kind not in (SELECT, MULTI_SELECT) and options is not None: raise QuestionnaireSchemaError(f"A pergunta {qkey!r} não aceita opções.")
            questions[qkey] = question
    for qkey, question in questions.items():
        condition = question.get("showIf")
        if condition is not None and (not isinstance(condition, dict) or condition.get("question") not in questions or "equals" not in condition or condition["question"] == qkey): raise QuestionnaireSchemaError(f"A condição de visibilidade de {qkey!r} é inválida.")
    return deepcopy(value)


def schema(configured: dict[str, Any] | None = None) -> dict[str, Any]:
    return validate_schema(configured) if configured else {"version": SCHEMA_VERSION, "sections": deepcopy(SECTIONS)}


def _questions(definition: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {question["key"]: question for section in definition["sections"] for question in section["questions"]}


def section_keys(definition: dict[str, Any]) -> frozenset[str]:
    return frozenset(section["key"] for section in definition["sections"])


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
    if kind == SELECT:
        return isinstance(value, str) and value in question["options"]
    if kind == MULTI_SELECT:
        return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item in question["options"] for item in value)
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 2000


def validate_answers(answers: dict[str, Any], definition: dict[str, Any] | None = None) -> dict[str, Any]:
    """Valida um preenchimento parcial. `None` limpa a resposta."""
    questions, clean = _questions(definition or schema()), {}
    for key, value in answers.items():
        question = questions.get(key)
        if question is None:
            raise QuestionnaireAnswerError(f"A pergunta «{key}» não existe neste questionário.")
        if value is None:
            continue
        if not _valid_value(question, value):
            raise QuestionnaireAnswerError(f"A resposta a «{question['label']}» não é válida.")
        clean[key] = value.strip() if isinstance(value, str) else value
    return clean


def merge_answers(current: dict[str, Any], incoming: dict[str, Any], definition: dict[str, Any] | None = None) -> dict[str, Any]:
    """Junta as respostas novas e retira as de perguntas que deixaram de se aplicar."""
    definition = definition or schema()
    questions = _questions(definition)
    merged = {**current, **validate_answers(incoming, definition)}
    for key, value in incoming.items():
        if value is None:
            merged.pop(key, None)
    return {
        key: value for key, value in merged.items() if _is_visible(questions[key], merged)
    }


def required_keys(answers: dict[str, Any], definition: dict[str, Any] | None = None) -> list[str]:
    return [
        question["key"]
        for section in (definition or schema())["sections"]
        for question in section["questions"]
        if question["required"] and _is_visible(question, answers)
    ]


def progress(answers: dict[str, Any], definition: dict[str, Any] | None = None) -> dict[str, int]:
    required = required_keys(answers, definition)
    return {"answered": sum(1 for key in required if key in answers), "required": len(required)}


def missing_labels(answers: dict[str, Any], definition: dict[str, Any] | None = None) -> list[str]:
    definition = definition or schema()
    questions = _questions(definition)
    return [questions[key]["label"] for key in required_keys(answers, definition) if key not in answers]


def has_declarations(answers: dict[str, Any], definition: dict[str, Any] | None = None) -> bool:
    return any(value is True for value in answers.values())
