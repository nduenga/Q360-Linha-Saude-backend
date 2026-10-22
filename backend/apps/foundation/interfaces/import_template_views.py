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

TEMPLATES = {
    "MEMBERS": {
        "sheet": "Pessoas seguras",
        "headers": ["Relação com o titular", "Nome", "Apelido", "Data de nascimento", "Sexo", "Referência externa"],
        "required": ["Relação com o titular", "Nome", "Apelido", "Data de nascimento"],
        "types": ["Texto/código", "Texto", "Texto", "Data", "Selecção", "Texto"],
        "example": ["TITULAR", "Ana", "Silva", "1990-05-21", "F", "REF-001"],
        "help": ["Código de relação configurado no tenant", "Texto obrigatório", "Texto obrigatório", "Data AAAA-MM-DD", "M ou F", "Texto opcional"],
    },
    "CLAIMS": {
        "sheet": "Sinistros",
        "headers": ["Data de ocorrência", "Código da cobertura", "Valor pago", "Referência do membro", "Valor provisionado", "Moeda", "Estado"],
        "required": ["Data de ocorrência", "Código da cobertura", "Valor pago"],
        "types": ["Data", "Texto/código", "Número decimal", "Texto", "Número decimal", "Selecção", "Selecção"],
        "example": ["2026-03-31", "HOSP_INT", 25000, "REF-001", 0, "AOA", "PAGO"],
        "help": ["Data AAAA-MM-DD ou DD/MM/AAAA", "Código existente na biblioteca de coberturas", "Número igual ou superior a zero", "Texto opcional", "Número igual ou superior a zero", "AOA ou USD; omissão = AOA", "PAGO, ABERTO ou REJEITADO; omissão = PAGO"],
    },
    "PREMIUMS": {
        "sheet": "Prémios",
        "headers": ["Início do período", "Fim do período", "Valor do prémio", "Número de segurados", "Moeda"],
        "required": ["Início do período", "Fim do período", "Valor do prémio"],
        "types": ["Data", "Data", "Número decimal", "Número inteiro", "Selecção"],
        "example": ["2026-01-01", "2026-12-31", 120000, 25, "AOA"],
        "help": ["Data AAAA-MM-DD ou DD/MM/AAAA", "Data AAAA-MM-DD ou DD/MM/AAAA", "Número superior a zero", "Número inteiro opcional", "AOA ou USD; omissão = AOA"],
    },
    "BENEFITS": {
        "sheet": "Coberturas",
        "headers": ["Código", "Nome", "Descrição", "Definição (JSON)", "Categoria"],
        "required": ["Código", "Nome"],
        "types": ["Texto/código", "Texto", "Texto", "Objecto JSON", "Selecção"],
        "example": ["CONSULTA_EXTRA", "Consulta adicional", "Cobertura complementar", "{}", "COMPLEMENTAR"],
        "help": ["Começa por letra; até 60 caracteres", "Texto obrigatório", "Texto opcional", "Objecto JSON válido; vazio = sem definição", "COMPLEMENTAR (coberturas base não podem ser criadas por importação)"],
    },
}


def build_template(kind: str, *, relationship_codes: list[str] | None = None) -> bytes:
    spec = TEMPLATES[kind.upper()]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = spec["sheet"]
    sheet.append(spec["headers"])
    sheet.append(spec["example"])
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
    for header, field_type, help_text, example in zip(spec["headers"], spec["types"], [help_by_field[h] for h in spec["headers"]], spec["example"]):
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
