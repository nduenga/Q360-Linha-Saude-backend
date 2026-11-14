"""Modelo Word (opção B): o GTE escreve o documento no Word, com marcas
`{{variável}}` onde quer os dados, e o sistema substitui-as.

Duas espécies de marcas:

* **Valores simples** — `{{client.name}}`, `{{policy.number}}`… trocam-se pelo valor.
* **Listas** — `{{insured.name}}`, `{{coverage.limits}}`, `{{installment.amount}}`…
  Uma **linha de tabela** (ou um **parágrafo**) que tenha uma marca de lista
  repete-se uma vez por elemento. Várias linhas-modelo consecutivas podem
  definir estilos alternados; listas de opções podem ocupar células lado a lado.

Limites: escreva cada marca de seguida, sem mudar de formato a meio; as marcas
dentro de caixas de texto e formas não são substituídas.
"""
from __future__ import annotations

import copy
import io
import re
import zipfile
from decimal import Decimal
from typing import Any, Iterable

from lxml import etree

from apps.quote.domain.proposal_template import VARIABLES as PROPOSAL_VARIABLES
from apps.quote.domain.proposal_template import InvalidTemplateError

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

COMMON_SCALARS = {
    "client.name": "Nome do cliente/tomador",
    "client.nif": "NIF ou identificação do cliente",
    "client.email": "Email do cliente",
    "client.phone": "Telefone do cliente",
    "plan.name": "Nome do plano",
    "plan.product": "Nome do produto",
    "plan.segment": "Segmento (Individual e Familiar / Grupo)",
    "plan.accessSystem": "Sistema de acesso (rede / reembolso / misto)",
    "plan.accessMode": "Modalidade resumida de acesso (rede / reembolso / misto)",
    "plan.accessDescription": "Descrição do regime de acesso",
    "coverage.hospitalizationCapital": "Capital contratado para hospitalização",
    "coverage.hospitalizationBasis": "Base do capital de hospitalização",
    "premium.total": "Prémio total (com moeda)",
    "premium.currency": "Moeda",
    "document.number": "Número do documento",
    "document.date": "Data de emissão do documento",
    "premium.totalText": "Pr\u00e9mio total formatado",
    "plan.tier": "N\u00edvel do plano",
    "plan.category": "Categoria do plano",
    "plan.networkRegions": "Regiões cobertas pela rede configurada",
    "insured.count": "Número de pessoas seguras",
}
PROPOSAL_SCALARS = {
    **COMMON_SCALARS,
    "document.templateLabel": "Nome comercial do modelo de proposta",
    **{k: v for k, v in PROPOSAL_VARIABLES.items() if k not in COMMON_SCALARS},
}
POLICY_SCALARS = {
    **COMMON_SCALARS,
    "quote.number": "Número da cotação de origem",
    "policy.number": "Número da apólice",
    "policy.status": "Estado da apólice",
    "policy.type": "Tipo (Individual / Grupo)",
    "policy.issueDate": "Data de emissão da apólice",
    "policy.startDate": "Início de vigência",
    "policy.endDate": "Fim de vigência",
    "policy.termMonths": "Duração em meses",
    "policy.paymentFrequency": "Fracionamento do prémio",
    "policy.totalPremium": "Prémio total anual",
    "signature.name": "Nome de quem assinou",
    "signature.document": "Documento de identificação de quem assinou",
    "signature.capacity": "Qualidade de quem assinou",
    "signature.date": "Data da assinatura",
    "payment.firstDate": "Data do pagamento da 1.ª prestação",
    "payment.firstMethod": "Meio de pagamento da 1.ª prestação",
    "payment.firstReference": "Referência do pagamento da 1.ª prestação",
}
SCALARS_BY_TYPE = {"QUOTE_PROPOSAL": PROPOSAL_SCALARS, "POLICY": POLICY_SCALARS}

GROUPS: dict[str, dict[str, Any]] = {
    "insured": {"label": "Pessoas seguras", "fields": {"name": "Nome", "relationship": "Relação", "age": "Idade", "status": "Estado", "eligibility": "Decisão de elegibilidade", "eligibilityDecisionText": "Resultado de elegibilidade", "eligibilityEvidence": "Evidência da elegibilidade", "clinicalQuestionnaireRequired": "Questionário clínico necessário", "medicalExamRequired": "Exame médico necessário", "preExistingMode": "Tratamento da condição preexistente", "preExistingText": "Texto da decisão", "preExistingCondition": "Condição declarada", "preExistingWaitingMonths": "Meses de carência", "preExistingLoadingPct": "Agravamento aplicado", "preExistingSublimit": "Sublimite aplicado"}},
    "coverage": {
        "label": "Coberturas contratadas",
        "fields": {"name": "Cobertura", "limits": "Capitais e limites", "participation": "Participação/franquia", "waiting": "Carência", "priorApproval": "Aprovação prévia (Sim/Não)", "category": "Categoria", "inclusion": "Tipo de inclusão", "regime": "Regime", "networkCopay": "Copagamento na rede", "reimbursementCopay": "Copagamento em reembolso", "networkCoinsurancePct": "Comparticipação da seguradora na rede (%)", "reimbursementCoinsurancePct": "Comparticipação da seguradora em reembolso (%)", "networkAnnualDeductible": "Franquia anual na rede", "reimbursementAnnualDeductible": "Franquia anual em reembolso", "destinations": "Destinos", "closedDiseaseList": "Lista de doenças cobertas", "maxDaysPerYear": "Dias máximos por ano", "timeDeductibleDays": "Franquia temporal em dias", "currency": "Moeda", "notes": "Notas", "excludedItems": "Itens exclu\u00eddos da cobertura", "indicative": "Valor indicativo"},
    },
    "coverageOption": {"label": "Disponibilidade das coberturas", "fields": {"name": "Cobertura", "category": "Categoria", "inclusion": "Tipo de inclusão", "contracted": "Contratada", "nonContractedReason": "Motivo para não contratar a cobertura opcional", "nonContractedReasonNote": "Detalhe do motivo"}},
    "premiumMember": {"label": "Pr\u00e9mio por pessoa", "fields": {"name": "Pessoa", "relationship": "Categoria de parentesco", "age": "Idade", "ageBand": "Escalão etário", "total": "Pr\u00e9mio calculado para a pessoa"}},
    "premiumCategory": {"label": "Pr\u00e9mio por categoria", "fields": {"relationship": "Categoria de parentesco", "count": "Quantidade de pessoas", "total": "Pr\u00e9mio agregado da categoria"}},
    "pricingLine": {"label": "Linhas do c\u00e1lculo do pr\u00e9mio", "fields": {"member": "Pessoa", "code": "C\u00f3digo do componente", "type": "Tipo", "base": "Base", "factor": "Fator", "adjustment": "Ajuste", "result": "Resultado acumulado", "ageBand": "Faixa et\u00e1ria efetivamente usada", "source": "Origem", "sourceVersion": "Vers\u00e3o da origem"}},
    "paymentOption": {"label": "Op\u00e7\u00f5es indicativas de pagamento", "fields": {"frequency": "Periodicidade", "count": "N\u00famero de presta\u00e7\u00f5es", "amount": "Valor por presta\u00e7\u00e3o", "total": "Total nesta periodicidade", "loadingPct": "Acr\u00e9scimo por fracionamento", "paymentSummary": "Resumo do fracionamento", "indicative": "Simula\u00e7\u00e3o indicativa"}},
    "adjustment": {"label": "Ajustes do pr\u00e9mio", "fields": {"text": "Ajuste aplicado"}},
    "participationOption": {"label": "Op\u00e7\u00e3o de participa\u00e7\u00e3o", "fields": {"code": "C\u00f3digo", "name": "Nome", "annualDeductible": "Franquia anual", "copayPerConsultation": "Copagamento por consulta", "reimbursementPct": "Percentagem de reembolso", "premiumAdjustmentPct": "Ajuste no pr\u00e9mio (%)", "hospitalOnly": "Aplic\u00e1vel apenas a hospitaliza\u00e7\u00e3o"}},
    "requiredDocument": {"label": "Documentos necess\u00e1rios", "fields": {"documentType": "Tipo de documento", "description": "Descri\u00e7\u00e3o"}},
    "businessText": {"label": "Informa\u00e7\u00f5es do produto", "fields": {"title": "T\u00edtulo", "text": "Texto"}},
    "installment": {
        "label": "Prestações do prémio (só na apólice)",
        "fields": {"no": "Número", "period": "Período", "dueDate": "Vencimento", "amount": "Valor", "status": "Estado"},
    },
    "exclusion": {"label": "Exclusões", "fields": {"text": "Texto"}},
    "condition": {"label": "Condições", "fields": {"text": "Texto"}},
    "waiting": {"label": "Períodos de carência", "fields": {"coverage": "Cobertura", "text": "Carência"}},
}
GROUPS["coverage"]["fields"].update({
    "capital": "Capital seguro resumido",
    "details": "Detalhe da cobertura",
    "coinsurance": "Comparticipação formatada",
    "copay": "Co-pagamento resumido",
})
GROUPS["premiumCategory"]["fields"].update({
    "profile": "Perfil da categoria segura",
    "perCapita": "Prémio médio por pessoa da categoria",
})
GROUP_FIELDS = {f"{g}.{f}" for g, spec in GROUPS.items() for f in spec["fields"]}


def format_insurer_money(value: Any, currency: str | None = "AOA") -> str:
    """Format monetary values in the Protteja template convention (amount, Kz)."""
    if value in (None, ""):
        return "—"
    code = (currency or "AOA").upper()
    amount = Decimal(str(value))
    digits = 0 if amount == amount.to_integral_value() else 2
    from shared.formatting import number

    return f"{number(amount, digits)} {'Kz' if code == 'AOA' else code}"


def _format_insurer_money_text(value: Any, currency: str | None = "AOA") -> Any:
    """Reformat a money string already localized by the quote content layer."""
    if not isinstance(value, str):
        return value
    symbol = "Kz" if (currency or "AOA").upper() == "AOA" else (currency or "AOA").upper()
    match = re.fullmatch(rf"\s*{re.escape(symbol)}\s+([\d.]+)(?:,([\d]{{1,2}}))?\s*", value)
    if not match:
        return value
    raw = match.group(1).replace(".", "")
    if match.group(2):
        raw += "." + match.group(2)
    return format_insurer_money(raw, currency)


def allowed_names(document_type: str) -> set[str]:
    return set(SCALARS_BY_TYPE.get(document_type, PROPOSAL_SCALARS)) | GROUP_FIELDS


def schema(document_type: str) -> dict[str, Any]:
    return {
        "scalars": SCALARS_BY_TYPE.get(document_type, PROPOSAL_SCALARS),
        "lists": {
            name: {"label": spec["label"], "fields": {f"{name}.{f}": label for f, label in spec["fields"].items()}}
            for name, spec in GROUPS.items()
            if not (name == "installment" and document_type != "POLICY")
        },
    }


# ------------------------------------------------------------------ leitura
def _open(data: bytes):
    from docx import Document

    try:
        return Document(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - qualquer ficheiro que o python-docx não abra
        raise InvalidTemplateError("O ficheiro não é um documento Word (.docx) válido") from exc


def _paragraph_text(paragraph) -> str:
    return "".join(run.text for run in paragraph.runs) if paragraph.runs else paragraph.text


def _iter_tables(container) -> Iterable:
    for table in container.tables:
        yield table
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_tables(cell)


def _iter_paragraphs(container) -> Iterable:
    yield from container.paragraphs
    for table in container.tables:
        for row in table.rows:
            seen = set()
            for cell in row.cells:
                if id(cell._tc) in seen:
                    continue
                seen.add(id(cell._tc))
                yield from _iter_paragraphs(cell)


def _containers(document) -> list:
    parts = [document]
    for section in document.sections:
        for part in (section.header, section.footer, section.first_page_header, section.first_page_footer,
                     section.even_page_header, section.even_page_footer):
            parts.append(part)
    return parts


def placeholders_in(data: bytes) -> set[str]:
    """Return markers from every Word story in the DOCX package.

    A prepared insurer model can place a marker in a text box, footnote or
    comment. Those parts are not all exposed by python-docx, so validation
    must read the same XML parts that the renderer updates.
    """
    found: set[str] = set()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            for entry in package.infolist():
                if not _is_word_text_part(entry.filename):
                    continue
                root = etree.fromstring(package.read(entry.filename))
                text = "".join(node.text or "" for node in root.xpath(".//w:t", namespaces=_W))
                found.update(PLACEHOLDER.findall(text))
    except (zipfile.BadZipFile, etree.XMLSyntaxError) as exc:
        raise InvalidTemplateError("O ficheiro nao e um documento Word (.docx) valido") from exc
    return found


def validate(data: bytes, document_type: str) -> dict[str, Any]:
    """Recusa marcas desconhecidas (nunca sai um documento com `{{buraco}}`)."""
    found = placeholders_in(data)
    unknown = sorted(found - allowed_names(document_type))
    if unknown:
        raise InvalidTemplateError(
            f"O modelo Word usa marcas desconhecidas: {unknown}. "
            f"Consulte as marcas permitidas em GET /document-templates/schema."
        )
    if not found:
        raise InvalidTemplateError("O modelo Word não tem nenhuma marca {{variável}}: nada seria preenchido")
    return {"placeholders": sorted(found)}


# ----------------------------------------------------------------- preencher
def _replace_in_paragraph(paragraph, resolve) -> None:
    full = _paragraph_text(paragraph)
    if "{{" not in full:
        return
    # Write only into Word's text nodes. Assigning ``Run.text`` clears every
    # child in that run, including drawings/anchors used for logos and page
    # backgrounds when a template placed text and artwork together.
    from docx.oxml.ns import qn

    text_tag = qn("w:t")
    control_tags = {qn("w:tab"): "\t", qn("w:br"): "\n", qn("w:cr"): "\n"}
    tokens = []
    # Match python-docx's Run.text semantics: inspect direct run children so
    # tabs or text inside an anchored drawing/text box do not shift offsets.
    for run in paragraph.runs:
        for element in run._r:
            if element.tag == text_tag:
                tokens.append((element, element.text or ""))
            elif element.tag in control_tags:
                tokens.append((element, control_tags[element.tag]))
    if not tokens:
        paragraph.add_run(PLACEHOLDER.sub(lambda m: resolve(m.group(1), m.group(0)), full))
        _disable_proofing(paragraph)
        return

    # Replace from right to left so earlier offsets stay valid. Rebuild the
    # affected text nodes only; all non-text XML (drawings, field codes, etc.)
    # remains untouched.
    for match in reversed(list(PLACEHOLDER.finditer(full))):
        current = "".join(value if element.tag != text_tag else element.text or "" for element, value in tokens)
        start, end = match.span()
        replacement = resolve(match.group(1), match.group(0))
        offset = 0
        first = None
        for node, token in tokens:
            value = node.text or "" if node.tag == text_tag else token
            node_start, node_end = offset, offset + len(value)
            offset = node_end
            if node_end <= start or node_start >= end:
                continue
            if node.tag != text_tag:
                continue
            if first is None:
                first = node
                prefix = value[: max(0, start - node_start)]
                suffix = value[max(0, end - node_start) :] if end <= node_end else ""
                node.text = prefix + replacement + suffix
            else:
                suffix = value[max(0, end - node_start) :] if end <= node_end else ""
                node.text = suffix
        # Empty/adjacent text nodes are valid; preserve them to avoid changing
        # run formatting and relationships around the placeholder.
    _disable_proofing(paragraph)


def _disable_proofing(paragraph) -> None:
    """Avoid editor spell-check marks becoming part of the visual review.

    A DOCX has no reliable ``pt-AO`` proofing dictionary across Word and
    LibreOffice. Dynamic names, NIFs, product terms and generated monetary
    values were consequently shown with red wavy underlines in some viewers.
    This function is used only on paragraphs with a marker. ``w:noProof``
    only controls proofing; it leaves styles, colours, drawings and page
    layout exactly as supplied by the insurer's template.
    """
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    no_proof_tag = qn("w:noProof")
    for run in paragraph.runs:
        properties = run._r.get_or_add_rPr()
        if properties.find(no_proof_tag) is None:
            properties.append(OxmlElement("w:noProof"))


def _group_of(text: str) -> str | None:
    for name in PLACEHOLDER.findall(text):
        head, separator, field = name.partition(".")
        # Scalar placeholders can share a prefix with a repeating group
        # (for example ``insured.count`` and ``insured.name``). Only fields
        # declared on the group may cause a row/paragraph to be expanded.
        if separator and head in GROUPS and field in GROUPS[head]["fields"]:
            return head
    return None


def _text_of_row(row) -> str:
    return " ".join(_paragraph_text(p) for cell in row.cells for p in cell.paragraphs)


def _group_resolver(group: str, item: dict[str, str], *, empty_value: str = "—"):
    def resolve(name: str, original: str) -> str:
        head, _, field = name.partition(".")
        if head == group:
            value = item.get(field)
            return empty_value if value in (None, "") else str(value)
        return original  # outras marcas ficam para a passagem dos valores simples

    return resolve


def _unique_row_cells(row):
    cells = []
    seen = set()
    for cell in row.cells:
        if id(cell._tc) in seen:
            continue
        seen.add(id(cell._tc))
        cells.append(cell)
    return cells


def _expand_lists(document, groups: dict[str, list[dict[str, str]]]) -> None:
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph

    # Linhas de tabela. Process all rows of a group in one pass so templates
    # can retain multiple row styles (for example alternating coverage bands).
    for table in list(_iter_tables(document)):
        rows_by_group: dict[str, list] = {}
        for row in list(table.rows):
            group = _group_of(_text_of_row(row))
            if group is not None:
                rows_by_group.setdefault(group, []).append(row)

        for group, template_rows in rows_by_group.items():
            items = groups.get(group, [])
            parent = template_rows[0]._tr.getparent()
            position = parent.index(template_rows[0]._tr)
            cells_by_row = [_unique_row_cells(row) for row in template_rows]
            marked_cell_indices = [
                [index for index, cell in enumerate(cells) if _group_of(" ".join(_paragraph_text(p) for p in cell.paragraphs)) == group]
                for cells in cells_by_row
            ]

            # The insurer's model uses one row of four cells for payment
            # frequencies and two columns for exclusions. Fill these matrices
            # horizontally while preserving the original table geometry.
            is_matrix = group in {"paymentOption", "exclusion"} and len(template_rows) == 1 and len(marked_cell_indices[0]) > 1
            generated_rows = []
            if is_matrix:
                template = template_rows[0]._tr
                columns = marked_cell_indices[0]
                row_count = (len(items) + len(columns) - 1) // len(columns)
                for row_index in range(row_count):
                    clone = copy.deepcopy(template)
                    generated_rows.append(clone)
                    # Resolve each marked cell against the corresponding item.
                    row_cells = list(clone.iter(qn("w:tc")))
                    for column_index, source_index in enumerate(columns):
                        target_tc = row_cells[source_index]
                        item_index = row_index * len(columns) + column_index
                        item = items[item_index] if item_index < len(items) else {}
                        resolve = _group_resolver(group, item)
                        for p in target_tc.iter(qn("w:p")):
                            _replace_in_paragraph(Paragraph(p, None), resolve)
            else:
                for item_index, item in enumerate(items):
                    source = template_rows[item_index % len(template_rows)]._tr
                    clone = copy.deepcopy(source)
                    generated_rows.append(clone)
                    resolve = _group_resolver(group, item)
                    for p in clone.iter(qn("w:p")):
                        _replace_in_paragraph(Paragraph(p, None), resolve)

            template_elements = [row._tr for row in template_rows]
            for element in template_elements:
                parent.remove(element)
            for offset, element in enumerate(generated_rows):
                parent.insert(position + offset, element)
    # Parágrafos fora de tabelas
    for paragraph in list(document.paragraphs):
        group = _group_of(_paragraph_text(paragraph))
        if group is None:
            continue
        element = paragraph._p
        parent = element.getparent()
        position = parent.index(element)
        for offset, item in enumerate(groups.get(group, [])):
            clone = copy.deepcopy(element)
            parent.insert(position + 1 + offset, clone)
            _replace_in_paragraph(Paragraph(clone, None), _group_resolver(group, item))
        parent.remove(element)


_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_W = {"w": _WORD_NS}


def _is_word_text_part(name: str) -> bool:
    # Do not touch styles, themes, numbering or relationships. Copying those
    # bytes verbatim is what preserves the insurer's exact visual layout.
    # Text boxes are stored inside document/header/footer XML; the remaining
    # entries below are the Word stories that can also contain paragraphs.
    return bool(
        re.fullmatch(
            r"word/(?:document|header\d+|footer\d+|footnotes|endnotes|comments|commentsExtended)\.xml",
            name,
        )
    )


def _set_xml_text(node, value: str) -> None:
    node.text = value
    space = f"{{{_XML_NS}}}space"
    if value[:1].isspace() or value[-1:].isspace():
        node.set(space, "preserve")
    elif space in node.attrib:
        del node.attrib[space]


def _mark_generated_runs(text_nodes) -> None:
    """Suppress spell-check only in runs that held a dynamic marker."""
    for node in text_nodes:
        runs = node.xpath("ancestor::w:r[1]", namespaces=_W)
        if not runs:
            continue
        run = runs[0]
        properties = run.find(f"{{{_WORD_NS}}}rPr")
        if properties is None:
            properties = etree.Element(f"{{{_WORD_NS}}}rPr")
            run.insert(0, properties)
        if properties.find(f"{{{_WORD_NS}}}noProof") is None:
            properties.append(etree.Element(f"{{{_WORD_NS}}}noProof"))


def _replace_xml_paragraph(paragraph, resolve) -> None:
    """Replace markers without creating or restyling a Word run."""
    nodes = paragraph.xpath(".//w:t", namespaces=_W)
    full = "".join(node.text or "" for node in nodes)
    matches = list(PLACEHOLDER.finditer(full))
    if not matches:
        return
    for match in reversed(matches):
        start, end = match.span()
        replacement = resolve(match.group(1), match.group(0))
        offset, placed, touched = 0, False, []
        for node in nodes:
            value = node.text or ""
            node_start, node_end = offset, offset + len(value)
            offset = node_end
            if node_end <= start or node_start >= end:
                continue
            touched.append(node)
            prefix = value[: max(0, start - node_start)] if not placed else ""
            suffix = value[max(0, end - node_start):] if end <= node_end else ""
            _set_xml_text(node, prefix + (replacement if not placed else "") + suffix)
            placed = True
        _mark_generated_runs(touched)


def _xml_group_of(element) -> str | None:
    text = "".join(node.text or "" for node in element.xpath(".//w:t", namespaces=_W))
    return _group_of(text)


def _fill_word_xml(data: bytes, scalar_resolve, groups: dict[str, list[dict[str, str]]]) -> bytes:
    root = etree.fromstring(data)
    # Avoid serialising a story that contains no marker at all. Besides being
    # faster, this keeps unrelated notes/comments byte-for-byte identical.
    if "{{" not in "".join(node.text or "" for node in root.xpath(".//w:t", namespaces=_W)):
        return data
    # Expand each group once per table. Multiple model rows can define
    # alternating band styles; copy those rows cyclically for the data.
    for table in root.xpath(".//w:tbl", namespaces=_W):
        rows_by_group: dict[str, list] = {}
        for row in table.xpath("./w:tr", namespaces=_W):
            group = _xml_group_of(row)
            if group is not None:
                rows_by_group.setdefault(group, []).append(row)

        for group, template_rows in rows_by_group.items():
            items = groups.get(group, [])
            parent = template_rows[0].getparent()
            position = parent.index(template_rows[0])
            marked_cell_indices = [
                [index for index, cell in enumerate(row.xpath("./w:tc", namespaces=_W))
                 if _xml_group_of(cell) == group]
                for row in template_rows
            ]
            is_matrix = (
                group in {"paymentOption", "exclusion"}
                and len(template_rows) == 1
                and len(marked_cell_indices[0]) > 1
            )
            generated_rows = []
            if is_matrix:
                template = template_rows[0]
                columns = marked_cell_indices[0]
                row_count = (len(items) + len(columns) - 1) // len(columns)
                for row_index in range(row_count):
                    clone = copy.deepcopy(template)
                    generated_rows.append(clone)
                    cells = clone.xpath("./w:tc", namespaces=_W)
                    for column_index, cell_index in enumerate(columns):
                        item_index = row_index * len(columns) + column_index
                        item = items[item_index] if item_index < len(items) else {}
                        resolver = _group_resolver(
                            group, item,
                            empty_value="" if item_index >= len(items) else "—",
                        )
                        for paragraph in cells[cell_index].xpath(".//w:p", namespaces=_W):
                            _replace_xml_paragraph(paragraph, resolver)
            else:
                for item_index, item in enumerate(items):
                    clone = copy.deepcopy(template_rows[item_index % len(template_rows)])
                    generated_rows.append(clone)
                    resolver = _group_resolver(group, item)
                    for paragraph in clone.xpath(".//w:p", namespaces=_W):
                        _replace_xml_paragraph(paragraph, resolver)

            for row in template_rows:
                parent.remove(row)
            for offset, row in enumerate(generated_rows):
                parent.insert(position + offset, row)
    for paragraph in reversed(list(root.xpath(".//w:p[not(ancestor::w:tr)]", namespaces=_W))):
        group = _xml_group_of(paragraph)
        if group is None:
            continue
        parent, position = paragraph.getparent(), paragraph.getparent().index(paragraph)
        for offset, item in enumerate(groups.get(group, [])):
            clone = copy.deepcopy(paragraph)
            parent.insert(position + offset, clone)
            _replace_xml_paragraph(clone, _group_resolver(group, item))
        parent.remove(paragraph)
    for paragraph in root.xpath(".//w:p", namespaces=_W):
        _replace_xml_paragraph(paragraph, scalar_resolve)
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)


def _fill_without_rewriting_template(data: bytes, scalars: dict[str, Any], groups: dict[str, list[dict[str, Any]]]) -> bytes:
    clean_groups = {
        group: [{key: "" if value is None else str(value) for key, value in item.items()} for item in items]
        for group, items in groups.items()
    }

    def scalar_resolve(name: str, _original: str) -> str:
        value = scalars.get(name)
        return "—" if value in (None, "") else str(value)

    source, output = io.BytesIO(data), io.BytesIO()
    with zipfile.ZipFile(source, "r") as original, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as copied:
        for entry in original.infolist():
            part = original.read(entry.filename)
            if _is_word_text_part(entry.filename):
                part = _fill_word_xml(part, scalar_resolve, clean_groups)
            copied.writestr(entry, part)
    return output.getvalue()


def fill(data: bytes, *, scalars: dict[str, Any], groups: dict[str, list[dict[str, Any]]]) -> bytes:
    """Replace markers without rebuilding the insurer's DOCX package."""
    return _fill_without_rewriting_template(data, scalars, groups)

    """Devolve o `.docx` com as marcas substituídas."""
    document = _open(data)
    clean_groups = {g: [{k: ("" if v is None else str(v)) for k, v in item.items()} for item in items] for g, items in groups.items()}
    _expand_lists(document, clean_groups)

    def resolve(name: str, original: str) -> str:
        if name not in scalars:
            return original
        value = scalars[name]
        return "—" if value in (None, "") else str(value)

    for container in _containers(document):
        for paragraph in _iter_paragraphs(container):
            _replace_in_paragraph(paragraph, resolve)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


# --------------------------------------------------------------- dados
def groups_from_content(content: dict[str, Any], *, policy_members: dict[str, str] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Listas a partir do conteúdo estruturado da proposta/apólice."""
    import json
    from shared.formatting import money

    def display(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return "Sim" if value else "Não"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    def age_band_label(value: Any) -> str | None:
        if value in (None, ""):
            return None
        match = re.fullmatch(r"(\d+)-(\d+)", str(value))
        if match:
            return f"{match.group(1)}–{match.group(2)} anos"
        match = re.fullmatch(r"(\d+)\+", str(value))
        if match:
            return f"{match.group(1)} ou mais anos"
        return str(value)

    status_labels = {
        "INCLUDED": "Incluída",
        "EXCLUDED": "Excluída",
        "REFERRAL": "Encaminhada para análise",
    }
    insured = []
    for person in content.get("population", []):
        status = person.get("status")
        pre_existing = person.get("preExisting") or {}
        if policy_members is not None:
            status = policy_members.get(person.get("memberId"), status)
        insured.append(
            {"name": person.get("name"), "relationship": person.get("relationship"),
             "age": person.get("age"), "status": status_labels.get(status, status),
             "eligibility": person.get("eligibilityDecision"),
             "eligibilityDecisionText": person.get("eligibilityDecisionText"),
             "eligibilityEvidence": display(person.get("eligibilityEvidence")),
             "clinicalQuestionnaireRequired": display(person.get("clinicalQuestionnaireRequired")),
             "medicalExamRequired": display(person.get("medicalExamRequired")),
             "preExistingMode": pre_existing.get("mode"), "preExistingText": pre_existing.get("text"),
             "preExistingCondition": pre_existing.get("condition"),
             "preExistingWaitingMonths": pre_existing.get("waitingMonths"),
             "preExistingLoadingPct": pre_existing.get("loadingPct"),
             "preExistingSublimit": pre_existing.get("sublimitAmount")}
        )
    coverage = []
    for c in content.get("coverages", []):
        contracted = bool(c.get("contracted"))
        non_contracted_label = "Não contratada"
        if c.get("nonContractedReason"):
            non_contracted_label += f": {c['nonContractedReason']}"
        if c.get("nonContractedReasonNote"):
            non_contracted_label += f" ({c['nonContractedReasonNote']})"
        network_pct = c.get("networkCoinsurancePct")
        reimbursement_pct = c.get("reimbursementCoinsurancePct")
        coinsurance = network_pct if network_pct not in (None, "") else reimbursement_pct
        if coinsurance not in (None, ""):
            coinsurance = f"{Decimal(str(coinsurance)).normalize():f}%"
        network_copay = c.get("networkCopay")
        reimbursement_copay = c.get("reimbursementCopay")
        copay = network_copay or reimbursement_copay
        capital_summary = c.get("summaryCapital") or {}
        limits = c.get("limits") or []
        inclusion_label = "Cobertura base" if c.get("inclusion") == "INCLUDED" else "Cobertura opcional"
        coverage.append({
            "name": c.get("name"),
            "capital": (
                "Não contratada" if not contracted else
                capital_summary.get("value") or (limits[0] if limits else "Conforme plano")
            ),
            "details": c.get("notes") or inclusion_label,
            "coinsurance": coinsurance if contracted and coinsurance else ("—" if not contracted else "Conforme plano"),
            "copay": _format_insurer_money_text(copay, c.get("currency")) if contracted and copay else ("—" if not contracted else "Conforme plano"),
            "limits": "; ".join(c.get("limits") or []) if contracted else "—",
            "participation": "; ".join(c.get("participation") or []) if contracted else "—",
            "waiting": c.get("waiting"),
            "priorApproval": "Sim" if c.get("requiresPriorApproval") else "Não",
            "networkCopay": c.get("networkCopay"), "reimbursementCopay": c.get("reimbursementCopay"),
            "networkCoinsurancePct": c.get("networkCoinsurancePct"),
            "reimbursementCoinsurancePct": c.get("reimbursementCoinsurancePct"),
            "networkAnnualDeductible": c.get("networkAnnualDeductible"),
            "reimbursementAnnualDeductible": c.get("reimbursementAnnualDeductible"),
            "category": c.get("category"), "inclusion": c.get("inclusion"),
            "regime": c.get("participationRegime") if contracted else non_contracted_label,
            "destinations": display(c.get("destinations")) if contracted else "—",
            "closedDiseaseList": display(c.get("closedDiseaseList")),
            "maxDaysPerYear": c.get("maxDaysPerYear"),
            "timeDeductibleDays": c.get("timeDeductibleDays"), "currency": c.get("currency"),
            "notes": c.get("notes"), "excludedItems": display(c.get("excludedItems")), "indicative": display(c.get("indicative")),
        })
    coverage_options = [
        {"name": c.get("name"), "category": c.get("category"), "inclusion": c.get("inclusion"),
         "contracted": display(c.get("contracted")),
         "nonContractedReason": c.get("nonContractedReason"),
         "nonContractedReasonNote": c.get("nonContractedReasonNote")}
        for c in content.get("coverages", [])
    ]
    population_by_id = {p.get("memberId"): p for p in content.get("population", [])}
    premium_members = content.get("premium", {}).get("members", [])
    premium_by_member = []
    for item in premium_members:
        person = population_by_id.get(item.get("memberId"), {})
        age_band = next((line.get("ageBand") for line in item.get("lines", []) if line.get("ageBand")), None)
        premium_by_member.append({
            "name": item.get("name"),
            "relationship": person.get("relationship"),
            "age": person.get("age"),
            "ageBand": age_band_label(age_band),
            "total": format_insurer_money(item.get("total"), content.get("premium", {}).get("currency")),
        })
    pricing_lines = []
    for line in content.get("premium", {}).get("quoteLevel", []):
        pricing_lines.append({"member": None, "code": line.get("code"), "type": line.get("type"),
                              "base": line.get("base"), "factor": line.get("factor"),
                              "adjustment": line.get("adjustment"), "result": line.get("result"),
                              "ageBand": None, "source": line.get("source"),
                              "sourceVersion": line.get("sourceVersion")})
    for item in premium_members:
        for line in item.get("lines", []):
            pricing_lines.append({"member": item.get("name"), "code": line.get("code"), "type": line.get("type"),
                                  "base": line.get("base"), "factor": line.get("factor"),
                                  "adjustment": line.get("adjustment"), "result": line.get("result"),
                                  "ageBand": line.get("ageBand"), "source": line.get("source"),
                                  "sourceVersion": line.get("sourceVersion")})
    participation_option = content.get("participationOption")
    participation_options = []
    if participation_option:
        participation_options.append({key: display(value) for key, value in participation_option.items()})
    required_documents = [
        {"documentType": row.get("documentType"), "description": row.get("description")}
        for row in content.get("requiredDocuments", [])
    ]
    business_texts = [
        {"title": row.get("title"), "text": row.get("text")}
        for row in content.get("businessTexts", [])
    ]
    currency = content.get("premium", {}).get("currency") or "AOA"
    payment_frequency_labels = {
        "ANUAL": "Anual",
        "SEMESTRAL": "Semestral",
        "TRIMESTRAL": "Trimestral",
        "MENSAL": "Mensal",
    }
    payment_options = []
    for row in content.get("premium", {}).get("paymentOptions", []):
        loading = row.get("loadingPct")
        count = row.get("count")
        summary = "fracção única" if count == 1 else f"× {count} fracções"
        if loading not in (None, "", "0", "0.0", "0.00"):
            summary += f" · +{display(loading)}%"
        payment_options.append({
            "frequency": payment_frequency_labels.get(row.get("frequency"), row.get("frequency")),
            "count": count,
            "amount": format_insurer_money(row.get("installmentAmount"), currency),
            "total": format_insurer_money(row.get("totalAmount"), currency),
            "loadingPct": loading,
            "paymentSummary": summary,
            "indicative": "Indicativo" if row.get("indicative") else "Não indicativo",
        })
    premium_categories = []
    ages_by_relationship: dict[str, list[int]] = {}
    for person in content.get("population", []):
        relationship = str(person.get("relationship") or "")
        if relationship and person.get("age") is not None:
            ages_by_relationship.setdefault(relationship, []).append(int(person["age"]))
    for row in content.get("premium", {}).get("byRelationship", []):
        relationship = str(row.get("relationship") or "")
        normalized = relationship.casefold()
        if "titular" in normalized or "tomador" in normalized or "employee" in normalized:
            category = "Colaboradores (titulares)"
        elif "cônjuge" in normalized or "conjuge" in normalized or "spouse" in normalized:
            category = "Cônjuges"
        elif "filho" in normalized or "child" in normalized:
            category = "Filhos"
        else:
            category = relationship
        ages = ages_by_relationship.get(relationship, [])
        profile = f"Idade média {round(sum(ages) / len(ages))} anos" if ages else "Conforme dados da cotação"
        count = int(row.get("count") or 0)
        total = Decimal(str(row.get("total") or "0"))
        premium_categories.append({
            "relationship": category,
            "profile": profile,
            "count": count,
            "perCapita": format_insurer_money(total / count, currency) if count else "—",
            "total": format_insurer_money(total, currency),
        })
    return {
        "insured": insured,
        "coverage": coverage,
        "coverageOption": coverage_options,
        "premiumMember": premium_by_member,
        "premiumCategory": premium_categories,
        "pricingLine": pricing_lines,
        "paymentOption": payment_options,
        "participationOption": participation_options,
        "requiredDocument": required_documents,
        "businessText": business_texts,
        "adjustment": [{"text": text} for text in content.get("premium", {}).get("adjustments", [])],
        "exclusion": [{"text": t} for t in content.get("exclusions", [])],
        "condition": [{"text": t} for t in content.get("conditions", [])],
        "waiting": [{"coverage": w.get("coverage"), "text": w.get("text")} for w in content.get("waiting", [])],
        "installment": [],
    }
