"""HTML renderer for insurer-branded Protteja proposal PDFs."""
from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

from django.template import engines

from apps.quote.application import proposal_layout

_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "quote" / "protteja_proposal.html"
_ASSET_PATH = Path(__file__).resolve().parents[1] / "static" / "quote" / "protteja"
_ASSETS = {"logo": "protteja-logo.png", "footer": "protteja-footer.png"}


def _asset_data_uri(name: str) -> str:
    data = (_ASSET_PATH / _ASSETS[name]).read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _cover_html(blocks: list[proposal_layout.Block], variables: dict[str, Any]) -> tuple[str, list[proposal_layout.Block]]:
    """Build the Protteja cover/summary blocks from the quote's resolved data."""
    intro = next((str(block[1]) for block in blocks if block[0] == "paragraph"), "")
    remaining: list[proposal_layout.Block] = []
    skipped_intro = False
    for block in blocks:
        if block[0] in ("brand", "title"):
            continue
        if block[0] == "paragraph" and not skipped_intro:
            skipped_intro = True
            continue
        remaining.append(block)
    # The generic summary section is represented in the insurer's cover and
    # opening section, where its key fields are laid out like the source DOCX.
    if remaining and remaining[0][0] == "heading":
        remaining.pop(0)
    if remaining and remaining[0][0] == "kv":
        remaining.pop(0)

    name = variables.get("plan.name") or "Proposta de Seguro de Saúde"
    product = variables.get("plan.product") or "Seguro de Saúde"
    segment = variables.get("plan.segment") or ""
    tier = variables.get("plan.tier") or variables.get("plan.category") or ""
    category = str(variables.get("plan.category") or "").casefold()
    quote_number = variables.get("quote.number") or "—"
    premium = variables.get("premium.totalText") or variables.get("premium.total") or "—"
    insured_count = variables.get("insured.count") or 0
    capital = variables.get("coverage.hospitalizationCapital") or "Ver coberturas"
    capital_basis = variables.get("coverage.hospitalizationBasis") or "Consulte as condições da cobertura"
    access_mode = variables.get("plan.accessMode") or "Conforme o plano"
    access_description = variables.get("plan.accessDescription") or variables.get("plan.accessSystem") or "Consulte as Condições Particulares"
    valid_until = variables.get("quote.validUntil") or "—"
    quote_date = variables.get("quote.date") or "—"
    client = variables.get("client.name") or "—"
    nif = variables.get("client.nif") or "—"

    tier_labels = ["Business", "Business Plus", "Premium", "Premium Plus"]
    searchable = f"{name} {tier}".casefold()
    active_tier = next((i for i, label in enumerate(tier_labels) if label.casefold() in searchable), None)
    if active_tier is None:
        active_tier = {"base": 0, "médio": 1, "medio": 1, "superior": 2}.get(str(tier).casefold())
    if active_tier is None:
        active_tier = {"colaboradores": 0, "quadros": 1, "administração": 3, "administracao": 3}.get(category)
    tier_text = {
        0: "NÍVEL 1/4 · BASE",
        1: "NÍVEL 2/4 · EQUILIBRADO",
        2: "NÍVEL 3/4 · SUPERIOR",
        3: "NÍVEL 4/4 · PREMIUM PLUS",
    }.get(active_tier, str(tier))
    tier_cells = "".join(
        f'<td class="{"active" if index == active_tier else ""}"><span>NÍVEL {index + 1}</span><strong>{label}</strong></td>'
        for index, label in enumerate(tier_labels)
    )

    opening_intro = intro or (
        f"A Protteja Seguros apresenta {client} a proposta do produto {product}, plano {name}, válida até {valid_until}."
    )
    product_label = str(product)
    if segment and str(segment).casefold() not in product_label.casefold():
        product_label = f"{product_label} · {segment}"

    cover = f"""
      <section class="cover">
        <div class="cover-topline"><span>SIMULAÇÃO · PROPOSTA COMERCIAL DE SEGURO DE SAÚDE</span></div>
        <h1>{_e(name)}</h1>
        <div class="cover-tags"><span>{_e(product_label)}</span>{f'<span>{_e(tier_text)}</span>' if tier_text else ''}</div>
        <p class="cover-intro">Coberturas, capitais e participação conforme os dados desta cotação.</p>
        <table class="cover-meta"><tbody><tr>
          <td><span>TOMADOR DO SEGURO</span><strong>{_e(client)}</strong></td>
          <td><span>REFERÊNCIA</span><strong>{_e(quote_number)}</strong></td>
          <td><span>DATA · VALIDADE</span><strong>{_e(quote_date)} · válida até {_e(valid_until)}</strong></td>
        </tr></tbody></table>
      </section>
      <table class="summary-cards"><tbody><tr>
        <td><div class="card-label">CAPITAL SEGURO · HOSPITALIZAÇÃO</div><div class="card-value">{_e(capital)}</div><div class="card-detail">{_e(capital_basis)}</div></td>
        <td><div class="card-label">PRÉMIO TOTAL ANUAL</div><div class="card-value">{_e(premium)}</div><div class="card-detail">{_e(insured_count)} pessoas seguras</div></td>
        <td><div class="card-label">REGIME DE ACESSO</div><div class="card-value">{_e(access_mode)}</div><div class="card-detail">{_e(access_description)}</div></td>
      </tr></tbody></table>
      <div class="tier-caption">POSICIONAMENTO NA GAMA SEGURO DE SAÚDE PROTTEJA</div>
      <table class="tier-table"><tbody><tr>{tier_cells}</tr></tbody></table>
      <section class="opening-section">
        <div class="eyebrow">01 · ENQUADRAMENTO</div>
        <h2>Nós cuidamos de si e da sua família</h2>
        <p>{_e(opening_intro)} Cotação {_e(quote_number)}.</p>
        <table class="key-value"><tbody>
          <tr><th>SEGURADORA</th><td>Protteja Seguros, S.A. · Certificado de Licença Nº 13/ISS/MF/12</td></tr>
          <tr><th>TOMADOR DO SEGURO</th><td>{_e(client)} · NIF {_e(nif)}</td></tr>
          <tr><th>PESSOAS SEGURAS</th><td>{_e(insured_count)} Pessoas Seguras</td></tr>
          <tr><th>RAMO / PRODUTO</th><td>{_e(product)} · {_e(name)}</td></tr>
        </tbody></table>
      </section>
    """
    return cover, remaining


def _blocks_html(blocks: list[proposal_layout.Block]) -> str:
    out: list[str] = []
    section_no = 1
    for block in blocks:
        kind = block[0]
        if kind == "heading":
            section_no += 1
            out.append(f'<section class="content-section"><div class="eyebrow">{section_no:02d} · {_e(block[1])}</div><h2>{_e(block[1])}</h2>')
        elif kind == "subheading":
            out.append(f'<h3>{_e(block[1])}</h3>')
        elif kind == "paragraph":
            out.append(f'<p>{_e(block[1])}</p>')
        elif kind == "note":
            out.append(f'<p class="note">{_e(block[1])}</p>')
        elif kind == "bullets":
            out.append('<ul class="detail-list">' + "".join(f"<li>{_e(item)}</li>" for item in block[1]) + "</ul>")
        elif kind == "kv":
            rows = "".join(f"<tr><th>{_e(key)}</th><td>{_e(value)}</td></tr>" for key, value in block[1])
            out.append(f'<table class="key-value"><tbody>{rows}</tbody></table>')
        elif kind == "table":
            headings = "".join(f"<th>{_e(value)}</th>" for value in block[1])
            rows = "".join("<tr>" + "".join(f"<td>{_e(value)}</td>" for value in row) + "</tr>" for row in block[2])
            out.append(f'<table class="data-table"><thead><tr>{headings}</tr></thead><tbody>{rows}</tbody></table>')
        elif kind == "signature":
            fields = "".join(f'<td><div class="signature-line"></div>{_e(label)}</td>' for label in block[1])
            out.append(f'<table class="signature-table"><tbody><tr>{fields}</tr></tbody></table>')
        if kind == "heading" and out:
            # Close the section wrapper when the next section heading begins.
            if len(out) > 1:
                out.insert(len(out) - 1, "</section>")
    if out:
        out.append("</section>")
    return "\n".join(out)


def render(blocks: list[proposal_layout.Block], *, title: str, variables: dict[str, Any] | None = None) -> bytes:
    """Render insurer-styled cover and proposal sections as self-contained HTML."""
    variables = variables or {}
    cover, remaining = _cover_html(blocks, variables)
    template = engines["django"].from_string(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    rendered = template.render({
        "title": title,
        "cover": cover,
        "proposal_body": _blocks_html(remaining),
        "logo_data": _asset_data_uri("logo"),
        "footer_data": _asset_data_uri("footer"),
        "header_label": variables.get("document.templateLabel") or f'{variables.get("plan.name") or "Proposta"} · {variables.get("plan.segment") or ""}',
        "quote_number": variables.get("quote.number") or "—",
    })
    return rendered.encode("utf-8")
