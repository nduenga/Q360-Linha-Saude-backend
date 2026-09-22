"""Friendly, customer-facing message texts — MOTOR_ELEGIBILIDADE.md
secção 2 ("Mensagens amigáveis"), "Regra de tom": nunca citar artigos de
lei, nunca usar a palavra "rejeitado" quando existe hipótese de correcção
(usar "falta", "ainda não", "precisamos de"), sempre dizer qual é o
próximo passo. Internal codes stay in `EligibilityMessage.code`; this
module only supplies the `severity`/`message` shown to the customer.

DOCUMENTO_INVALIDO/PROPOSTA_ANONIMA/NIF_INATIVO/VINCULO_LABORAL_INATIVO
are kept here ready for Fase C (compliance/payroll checks), even though
`evaluation.py` does not produce them yet — see MOTOR_ELEGIBILIDADE.md
"Fases de implementação".
"""
from __future__ import annotations

from typing import Any

_TEMPLATES: dict[str, tuple[str, str]] = {
    # code: (severity, template)
    "FALTA_CERTIFICADO_MATRICULA": (
        "WARNING",
        "Só falta mais uma coisa: envie uma foto do certificado de matrícula "
        "do seu filho(a), porque ele(a) já celebrou {limite} anos.",
    ),
    "FALTA_HOMOLOGACAO_UNIAO_FACTO": (
        "WARNING",
        "Para incluir o seu cônjuge/parceiro(a), precisamos de um documento "
        "que comprove a vossa união — pode ser da conservatória ou do "
        "tribunal.",
    ),
    "FALTA_PROVA_DEPENDENCIA_ASCENDENTE": (
        "WARNING",
        "Para incluir os seus pais/avós, envie um documento que mostre que "
        "vivem consigo ou que dependem de si financeiramente.",
    ),
    "IDADE_ACIMA_LIMITE_DEPENDENTE": (
        "ERROR",
        "Infelizmente, o seu dependente já não se enquadra na idade máxima "
        "permitida para esta cobertura ({limite} anos).",
    ),
    "ELIGIBLE_COM_AGRAVAMENTO": (
        "INFO",
        "Está tudo pronto! Devido a uma condição de saúde já existente, o "
        "prémio tem um pequeno acréscimo de {percentual}%.",
    ),
    "PENDENTE_JUNTA_MEDICA": (
        "WARNING",
        "Precisamos de uma avaliação médica adicional antes de confirmar a "
        "sua cobertura completa — a nossa equipa entra em contacto em "
        "breve.",
    ),
    "DOCUMENTO_INVALIDO": (
        "ERROR",
        "Precisamos de um Bilhete de Identidade válido (ou Cartão de "
        "Residente/Passaporte com Visto de Trabalho, se for estrangeiro).",
    ),
    "PROPOSTA_ANONIMA": (
        "ERROR",
        "Por razões de segurança, todas as propostas de seguro precisam de "
        "identificação completa.",
    ),
    "NIF_INATIVO": (
        "ERROR",
        "O seu NIF parece estar inactivo. Contacte a Administração Geral "
        "Tributária para regularizar antes de continuar.",
    ),
    "VINCULO_LABORAL_INATIVO": (
        "ERROR",
        "Não conseguimos confirmar o seu vínculo actual com a empresa. "
        "Fale com o departamento de Recursos Humanos para actualizar o "
        "seu registo.",
    ),
}


def friendly_text(code: str, **params: Any) -> tuple[str, str]:
    """(severity, message) for a Fase-A Angola code. Falls back to the raw
    code as the message (severity WARNING) if `code` is not in the table,
    so an unmapped code never raises."""
    severity, template = _TEMPLATES.get(code, ("WARNING", code))
    try:
        return severity, template.format(**params)
    except (KeyError, IndexError):
        return severity, template
