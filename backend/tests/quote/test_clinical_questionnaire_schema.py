import pytest

from apps.quote.domain import clinical_questionnaire as form


SCHEMA = {
    "version": "v2",
    "sections": [{
        "key": "health", "label": "Saúde", "questions": [
            {"key": "hasCondition", "label": "Tem condição?", "type": "YES_NO", "required": True},
            {"key": "condition", "label": "Qual?", "type": "TEXT", "required": True,
             "showIf": {"question": "hasCondition", "equals": True}},
            {"key": "bloodType", "label": "Grupo sanguíneo", "type": "SELECT", "required": False,
             "options": ["A", "B", "AB", "O"]},
        ],
    }],
}


def test_configured_schema_validates_conditional_and_choice_answers():
    definition = form.schema(SCHEMA)
    answers = form.merge_answers({}, {"hasCondition": False, "condition": None, "bloodType": "O"}, definition)
    assert answers == {"hasCondition": False, "bloodType": "O"}
    assert form.progress(answers, definition) == {"answered": 1, "required": 1}


def test_schema_rejects_duplicate_question_keys():
    invalid = {**SCHEMA, "sections": [{**SCHEMA["sections"][0], "questions": [
        *SCHEMA["sections"][0]["questions"], {"key": "hasCondition", "label": "Duplicada", "type": "TEXT"}
    ]}]}
    with pytest.raises(form.QuestionnaireSchemaError):
        form.validate_schema(invalid)
