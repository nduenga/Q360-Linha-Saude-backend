"""Excel templates for structured data imports."""
from __future__ import annotations

from io import BytesIO

from django.http import HttpResponse
from openpyxl import Workbook
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_scope

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Dados de teste fictícios: o modelo descarregado já traz várias linhas
# válidas, para se poder importar logo e experimentar a plataforma. As
# referências dos membros (REF-...) são as mesmas nos sinistros, e os códigos
# de cobertura existem no catálogo de mercado (market_catalog).
MEMBER_EXAMPLES = [
    ["TITULAR", "Ana", "Silva", "1985-05-21", "F", "REF-001"],
    ["CONJUGE", "Paulo", "Silva", "1983-11-02", "M", "REF-002"],
    ["FILHO", "Marta", "Silva", "2012-03-14", "F", "REF-003"],
    ["FILHO", "João", "Silva", "2016-08-30", "M", "REF-004"],
    ["TITULAR", "Carlos", "Mendes", "1978-01-09", "M", "REF-005"],
    ["CONJUGE", "Teresa", "Mendes", "1980-06-17", "F", "REF-006"],
    ["FILHO", "Nuno", "Mendes", "2005-12-01", "M", "REF-007"],
    ["ASCENDENTE", "Rosa", "Mendes", "1952-04-25", "F", "REF-008"],
    ["TITULAR", "Isabel", "Costa", "1992-09-12", "F", "REF-009"],
    ["FILHO", "Tiago", "Costa", "2019-02-07", "M", "REF-010"],
    ["TITULAR", "Manuel", "Domingos", "1969-07-30", "M", "REF-011"],
    ["CONJUGE", "Luísa", "Domingos", "1971-10-05", "F", "REF-012"],
    ["TITULAR", "Helena", "Neto", "1995-03-22", "F", "REF-013"],
    ["TITULAR", "Rui", "Fernandes", "1988-12-15", "M", "REF-014"],
    ["CONJUGE", "Sara", "Fernandes", "1990-01-28", "F", "REF-015"],
    ["FILHO", "Beatriz", "Fernandes", "2018-05-19", "F", "REF-016"],
    ["FILHO", "Daniel", "Fernandes", "2021-09-03", "M", "REF-017"],
    ["TITULAR", "Pedro", "Lopes", "1975-02-11", "M", "REF-018"],
    ["OUTRO", "Clara", "Lopes", "2001-07-08", "F", "REF-019"],
    ["TITULAR", "Joana", "Pires", "1999-11-27", "F", "REF-020"],
]

CLAIM_EXAMPLES = [
    ["2024-02-12", "OUTPATIENT", 18000, "REF-001", 0, "AOA", "PAGO"],
    ["2024-03-05", "PHARMACY", 9500, "REF-003", 0, "AOA", "PAGO"],
    ["2024-05-20", "HOSPITALIZATION", 450000, "REF-005", 0, "AOA", "PAGO"],
    ["2024-07-14", "EMERGENCY", 65000, "REF-010", 0, "AOA", "PAGO"],
    ["2024-09-01", "DENTAL", 32000, "REF-009", 0, "AOA", "PAGO"],
    ["2024-11-18", "ENDEMIC_DISEASES", 27000, "REF-004", 0, "AOA", "PAGO"],
    ["2025-01-22", "MATERNITY", 380000, "REF-015", 0, "AOA", "PAGO"],
    ["2025-02-10", "OUTPATIENT", 15000, "REF-008", 0, "AOA", "PAGO"],
    ["2025-03-28", "OPTICAL", 42000, "REF-011", 0, "AOA", "PAGO"],
    ["2025-05-06", "AMBULATORY_SURGERY", 210000, "REF-012", 0, "AOA", "PAGO"],
    ["2025-06-19", "PHARMACY", 12500, "REF-016", 0, "AOA", "PAGO"],
    ["2025-08-02", "PHYSIOTHERAPY", 54000, "REF-018", 0, "AOA", "PAGO"],
    ["2025-09-15", "CHECKUP_PREVENTIVE", 25000, "REF-013", 0, "AOA", "PAGO"],
    ["2025-10-30", "ALTERNATIVE_MEDICINE", 20000, "REF-019", 0, "AOA", "REJEITADO"],
    ["2025-12-09", "MEDICAL_EVACUATION", 8500, "REF-008", 0, "USD", "PAGO"],
    ["2026-01-17", "ENDEMIC_DISEASES", 31000, "REF-017", 0, "AOA", "PAGO"],
    ["2026-03-04", "HOSPITALIZATION", 520000, "REF-011", 0, "AOA", "PAGO"],
    ["2026-05-21", "OUTPATIENT", 19000, "REF-020", 0, "AOA", "PAGO"],
    ["2026-07-08", "EMERGENCY", 0, "REF-014", 85000, "AOA", "ABERTO"],
    ["2026-09-12", "CRITICAL_ILLNESS", 0, "REF-005", 1200000, "AOA", "ABERTO"],
]

PREMIUM_EXAMPLES = [
    ["2023-01-01", "2023-12-31", 4100000, 16, "AOA"],
    ["2024-01-01", "2024-12-31", 4650000, 18, "AOA"],
    ["2025-01-01", "2025-12-31", 5300000, 19, "AOA"],
    ["2026-01-01", "2026-12-31", 5900000, 20, "AOA"],
]

BENEFIT_EXAMPLES = [
    ["CONSULTA_EXTRA", "Consulta adicional", "Consultas de clínica geral além do limite do plano", "{}", "COMPLEMENTAR"],
    ["NUTRICAO", "Nutrição e dietética", "Consultas de nutrição com prescrição médica",
     '{"guaranteeForm": "ANNUAL_PER_PERSON", "typicalSublimits": ["Até 6 consultas por ano"], "requiresPriorApproval": false}', "COMPLEMENTAR"],
    ["TERAPIA_FALA", "Terapia da fala", "Sessões de terapia da fala para crianças e adultos",
     '{"guaranteeForm": "ANNUAL_PER_PERSON", "typicalWaitingDays": {"individual": [60, 90], "group": [0, 30]}, "requiresPriorApproval": true}', "COMPLEMENTAR"],
    ["PODOLOGIA", "Podologia", "Consultas e tratamentos de podologia", '{"exclusions": ["Tratamentos estéticos"]}', "COMPLEMENTAR"],
    ["APOIO_DOMICILIARIO", "Apoio de enfermagem ao domicílio", "Cuidados de enfermagem em casa após internamento",
     '{"allowedCurrencies": ["AOA"], "requiresPriorApproval": true}', "COMPLEMENTAR"],
    ["MEDICINA_DESPORTIVA", "Medicina desportiva", "Avaliação e acompanhamento de lesões desportivas", "", "COMPLEMENTAR"],
]

TEMPLATES = {
    "MEMBERS": {
        "sheet": "Pessoas seguras",
        "headers": ["Relação com o titular", "Nome", "Apelido", "Data de nascimento", "Sexo", "Referência externa"],
        "required": ["Relação com o titular", "Nome", "Apelido", "Data de nascimento"],
        "types": ["Texto/código", "Texto", "Texto", "Data", "Selecção", "Texto"],
        "examples": MEMBER_EXAMPLES,
        "help": ["Código de relação configurado no tenant", "Texto obrigatório", "Texto obrigatório", "Data AAAA-MM-DD", "M ou F", "Texto opcional"],
    },
    "CLAIMS": {
        "sheet": "Sinistros",
        "headers": ["Data de ocorrência", "Código da cobertura", "Valor pago", "Referência do membro", "Valor provisionado", "Moeda", "Estado"],
        "required": ["Data de ocorrência", "Código da cobertura", "Valor pago"],
        "types": ["Data", "Texto/código", "Número decimal", "Texto", "Número decimal", "Selecção", "Selecção"],
        "examples": CLAIM_EXAMPLES,
        "help": ["Data AAAA-MM-DD ou DD/MM/AAAA", "Código existente na biblioteca de coberturas", "Número igual ou superior a zero", "Texto opcional", "Número igual ou superior a zero", "AOA ou USD; omissão = AOA", "PAGO, ABERTO ou REJEITADO; omissão = PAGO"],
    },
    "PREMIUMS": {
        "sheet": "Prémios",
        "headers": ["Início do período", "Fim do período", "Valor do prémio", "Número de segurados", "Moeda"],
        "required": ["Início do período", "Fim do período", "Valor do prémio"],
        "types": ["Data", "Data", "Número decimal", "Número inteiro", "Selecção"],
        "examples": PREMIUM_EXAMPLES,
        "help": ["Data AAAA-MM-DD ou DD/MM/AAAA", "Data AAAA-MM-DD ou DD/MM/AAAA", "Número superior a zero", "Número inteiro opcional", "AOA ou USD; omissão = AOA"],
    },
    "BENEFITS": {
        "sheet": "Coberturas",
        "headers": ["Código", "Nome", "Descrição", "Definição (JSON)", "Categoria"],
        "required": ["Código", "Nome"],
        "types": ["Texto/código", "Texto", "Texto", "Objecto JSON", "Selecção"],
        "examples": BENEFIT_EXAMPLES,
        "help": ["Começa por letra; até 60 caracteres", "Texto obrigatório", "Texto opcional", "Objecto JSON válido; vazio = sem definição", "COMPLEMENTAR (coberturas base não podem ser criadas por importação)"],
    },
}


def build_template(kind: str, *, relationship_codes: list[str] | None = None) -> bytes:
    spec = TEMPLATES[kind.upper()]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = spec["sheet"]
    sheet.append(spec["headers"])
    for row in spec["examples"]:
        sheet.append(row)
    for cell in sheet[1]:
        cell.font = cell.font.copy(bold=True, color="FFFFFF")
        cell.fill = cell.fill.copy(fill_type="solid", fgColor="246B5B")
    for index, header in enumerate(spec["headers"], start=1):
        sheet.column_dimensions[chr(64 + index)].width = max(20, min(38, len(header) + 5))
    instructions = workbook.create_sheet("Instruções")
    instructions.append(["Campo", "Obrigatoriedade", "Tipo de dado", "Formato e valores permitidos", "Exemplo"])
    help_by_field = dict(zip(spec["headers"], spec["help"]))
    if kind.upper() == "MEMBERS" and relationship_codes:
        help_by_field["Relação com o titular"] = f"Escolha um código: {', '.join(relationship_codes)}."
    for header, field_type, help_text, example in zip(spec["headers"], spec["types"], [help_by_field[h] for h in spec["headers"]], spec["examples"][0]):
        instructions.append([header, "Obrigatório" if header in spec["required"] else "Opcional", field_type, help_text, example])
    for cell in instructions[1]:
        cell.font = cell.font.copy(bold=True)
    instructions.column_dimensions["A"].width = 32
    instructions.column_dimensions["B"].width = 18
    instructions.column_dimensions["C"].width = 20
    instructions.column_dimensions["D"].width = 76
    instructions.column_dimensions["E"].width = 32
    out = BytesIO()
    workbook.save(out)
    return out.getvalue()


class ImportTemplateView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, kind: str):
        key = kind.upper()
        spec = TEMPLATES.get(key)
        if spec is None:
            return Response({"detail": "Modelo inexistente. Use MEMBERS, CLAIMS, PREMIUMS ou BENEFITS."}, status=404)
        relationship_codes = None
        if key == "MEMBERS":
            from apps.client.application.relationship_service import list_relationship_codes
            relationship_codes = ["TITULAR", *(item.code for item in list_relationship_codes())]
        response = HttpResponse(build_template(key, relationship_codes=relationship_codes), content_type=XLSX)
        response["Content-Disposition"] = f'attachment; filename="modelo-{key.lower()}.xlsx"'
        return response
