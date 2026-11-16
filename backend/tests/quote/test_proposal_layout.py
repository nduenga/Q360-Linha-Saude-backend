from __future__ import annotations

from apps.quote.application.proposal_layout import variables_for


def test_word_proposal_cover_uses_dot_date_and_validity_days():
    values = variables_for(
        {
            "meta": {
                "quoteNumber": "COT-6",
                "quoteDate": "2026-11-13",
                "validUntil": "2026-12-13",
                "quoteType": "Novo negócio",
                "scenario": None,
            },
            "client": {"name": "Cliente", "nif": "1"},
            "plan": {"name": "Business", "product": "Saúde", "segment": "Individual"},
            "premium": {"totalText": "Kz 100,00", "currency": "AOA"},
            "population": [],
        },
        document_number="DOC-1",
        generated_on="2026-11-13",
    )

    assert values["quote.date"] == "13.11.2026"
    assert values["quote.validityDays"] == "30 dias"
    assert values["quote.validUntil"] == "13/12/2026"
