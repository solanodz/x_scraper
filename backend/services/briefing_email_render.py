"""Render puro: Briefing + FX USD/ARS → subject / text / HTML (Morning Briefing Email)."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any

# Solo casas USD/ARS del payload ars_usd (nunca Frankfurter / EUR / BRL).
_ARS_LABELS: tuple[tuple[str, str], ...] = (
    ("oficial", "Oficial"),
    ("blue", "Blue"),
    ("mep", "MEP"),
    ("ccl", "CCL"),
    ("tarjeta", "Tarjeta"),
)

_FX_UNAVAILABLE = "Dólar: no disponible"

_DISCLAIMER = (
    "Cotizaciones con demora posible (Market Data / fuentes FX). "
    "Esto no es consejo de inversión."
)

_WRAPPER_STYLE = (
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;"
    "font-size:15px;line-height:1.55;color:#18181b;max-width:640px;margin:0 auto;"
)
_H2_STYLE = (
    "font-size:18px;font-weight:700;margin:28px 0 10px;padding-bottom:6px;"
    "border-bottom:1px solid #e4e4e7;color:#09090b;"
)
_H3_STYLE = "font-size:15px;font-weight:600;margin:18px 0 6px;color:#27272a;"
_P_STYLE = "margin:0 0 10px;color:#27272a;"
_UL_STYLE = "margin:0 0 12px;padding-left:20px;color:#27272a;"
_LI_STYLE = "margin:0 0 6px;"
_MUTED_STYLE = "font-size:12px;color:#71717a;margin:8px 0 0;"
_CTA_STYLE = "margin:24px 0 8px;"
_BTN_STYLE = (
    "display:inline-block;padding:10px 14px;margin:0 8px 8px 0;"
    "background:#18181b;color:#fafafa;text-decoration:none;"
    "border-radius:6px;font-size:13px;font-weight:600;"
)
_FX_TABLE_STYLE = (
    "width:100%;border-collapse:collapse;margin:0 0 8px;font-size:14px;"
)
_FX_TD_STYLE = "padding:8px 10px;border-bottom:1px solid #f4f4f5;"
_FX_TD_LABEL = _FX_TD_STYLE + "font-weight:600;color:#18181b;"
_FX_TD_VAL = (
    _FX_TD_STYLE
    + "text-align:right;font-variant-numeric:tabular-nums;color:#3f3f46;"
)


def _fmt_price(value: Any) -> str | None:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n == int(n):
        return f"{int(n):,}".replace(",", ".")
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_fx_ars_block(fx_payload: dict) -> str:
    """Bloque markdown de dólar USD/ARS (oficial/blue/MEP/CCL/tarjeta)."""
    if not isinstance(fx_payload, dict):
        return _FX_UNAVAILABLE
    if fx_payload.get("error"):
        return _FX_UNAVAILABLE

    quotes = fx_payload.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        return _FX_UNAVAILABLE

    by_label: dict[str, dict[str, Any]] = {}
    for item in quotes:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("casa") or "").strip().lower()
        if label in {"bolsa"}:
            label = "mep"
        if label in {"contadoconliqui", "contado con liqui"}:
            label = "ccl"
        if label:
            by_label[label] = item

    lines: list[str] = ["## Dólar (USD/ARS)", ""]
    any_row = False
    for key, display in _ARS_LABELS:
        item = by_label.get(key)
        if not item:
            continue
        bid = _fmt_price(item.get("bid"))
        ask = _fmt_price(item.get("ask"))
        if bid is None and ask is None:
            continue
        any_row = True
        if bid is not None and ask is not None:
            price = f"compra {bid} / venta {ask}"
        elif ask is not None:
            price = f"venta {ask}"
        else:
            price = f"compra {bid}"
        lines.append(f"- **{display}**: {price}")

    if not any_row:
        return _FX_UNAVAILABLE

    source = str(fx_payload.get("source") or "dolarapi.com").strip()
    stamp = fx_payload.get("fetched_at") or next(
        (
            q.get("updated_at")
            for q in quotes
            if isinstance(q, dict) and q.get("updated_at")
        ),
        None,
    )
    lines.append("")
    if stamp:
        stamp_s = str(stamp).replace("T", " ").split(".")[0].replace("+00:00", " UTC")
        lines.append(f"_Fuente: {source} · {stamp_s}_")
    else:
        lines.append(f"_Fuente: {source}_")
    return "\n".join(lines)


def build_email_subject(*, now_local: datetime, has_prioridad_alta: bool = False) -> str:
    """Asunto: ``Briefing · DD/MM`` (+ hint opcional de prioridad alta)."""
    subject = f"Briefing · {now_local.strftime('%d/%m')}"
    if has_prioridad_alta:
        subject += " · prioridad alta"
    return subject


def _normalize_base_url(frontend_base_url: str) -> str:
    return (frontend_base_url or "").strip().rstrip("/")


def _rewrite_dossier_href(href: str, frontend_base_url: str) -> str:
    """``dossier:SYMBOL`` → link real al Dossier en la web."""
    raw = (href or "").strip()
    if raw.lower().startswith("dossier:"):
        symbol = raw.split(":", 1)[1].strip().upper()
        base = _normalize_base_url(frontend_base_url)
        if symbol and base:
            return f"{base}/dossier?ticker={symbol}"
    return raw


def _inline_md(text: str, *, frontend_base_url: str = "") -> str:
    """Escape + links ``[t](url)`` + **bold** + italic."""
    parts: list[str] = []
    pos = 0
    link_re = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    for m in link_re.finditer(text):
        parts.append(_inline_fmt_escaped(text[pos : m.start()]))
        label = html.escape(m.group(1))
        href = _rewrite_dossier_href(m.group(2), frontend_base_url)
        href_esc = html.escape(href, quote=True)
        parts.append(
            f'<a href="{href_esc}" style="color:#2563eb;text-decoration:underline;">'
            f"{label}</a>"
        )
        pos = m.end()
    parts.append(_inline_fmt_escaped(text[pos:]))
    return "".join(parts)


def _inline_fmt_escaped(text: str) -> str:
    chunks: list[str] = []
    pos = 0
    bold_re = re.compile(r"\*\*([^*]+)\*\*")
    for m in bold_re.finditer(text):
        chunks.append(_escape_with_italic(text[pos : m.start()]))
        chunks.append(f"<strong>{html.escape(m.group(1))}</strong>")
        pos = m.end()
    chunks.append(_escape_with_italic(text[pos:]))
    return "".join(chunks)


def _escape_with_italic(text: str) -> str:
    parts: list[str] = []
    pos = 0
    ital_re = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)|_([^_]+)_")
    for m in ital_re.finditer(text):
        parts.append(html.escape(text[pos : m.start()]))
        inner = m.group(1) or m.group(2) or ""
        parts.append(f"<em>{html.escape(inner)}</em>")
        pos = m.end()
    parts.append(html.escape(text[pos:]))
    return "".join(parts)


def _markdown_to_html(md: str, *, frontend_base_url: str = "") -> str:
    """Conversión línea a línea (soporta ## pegado a ### sin línea en blanco)."""
    lines = (md or "").replace("\r\n", "\n").split("\n")
    out: list[str] = []
    list_items: list[str] = []
    para_lines: list[str] = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            items = "".join(
                f'<li style="{_LI_STYLE}">{item}</li>' for item in list_items
            )
            out.append(f'<ul style="{_UL_STYLE}">{items}</ul>')
            list_items = []

    def flush_para() -> None:
        nonlocal para_lines
        if para_lines:
            body = "<br/>".join(para_lines)
            out.append(f'<p style="{_P_STYLE}">{body}</p>')
            para_lines = []

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            flush_list()
            flush_para()
            continue

        heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading:
            flush_list()
            flush_para()
            level = len(heading.group(1))
            style = _H2_STYLE if level <= 2 else _H3_STYLE
            tag = "h2" if level <= 2 else "h3"
            out.append(
                f'<{tag} style="{style}">'
                f"{_inline_md(heading.group(2), frontend_base_url=frontend_base_url)}"
                f"</{tag}>"
            )
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet:
            flush_para()
            list_items.append(
                _inline_md(bullet.group(1), frontend_base_url=frontend_base_url)
            )
            continue

        flush_list()
        para_lines.append(
            _inline_md(stripped, frontend_base_url=frontend_base_url)
        )

    flush_list()
    flush_para()
    return "\n".join(out)


def _fx_block_to_html(fx_payload: dict) -> str:
    """Tabla limpia para el bloque FX."""
    md = format_fx_ars_block(fx_payload)
    if md == _FX_UNAVAILABLE:
        return (
            f'<p style="{_P_STYLE}"><em>{html.escape(_FX_UNAVAILABLE)}</em></p>'
        )

    rows: list[tuple[str, str]] = []
    source_line = ""
    for line in md.split("\n"):
        m = re.match(r"^-\s+\*\*([^*]+)\*\*:\s+(.+)$", line.strip())
        if m:
            rows.append((m.group(1), m.group(2)))
            continue
        if line.strip().startswith("_Fuente:"):
            source_line = line.strip().strip("_")

    parts = [f'<h2 style="{_H2_STYLE}">Dólar (USD/ARS)</h2>']
    if rows:
        trs = []
        for label, val in rows:
            trs.append(
                "<tr>"
                f'<td style="{_FX_TD_LABEL}">{html.escape(label)}</td>'
                f'<td style="{_FX_TD_VAL}">{html.escape(val)}</td>'
                "</tr>"
            )
        parts.append(
            f'<table style="{_FX_TABLE_STYLE}" role="presentation">'
            + "".join(trs)
            + "</table>"
        )
    if source_line:
        parts.append(
            f'<p style="{_MUTED_STYLE}">{html.escape(source_line)}</p>'
        )
    return "\n".join(parts)


def build_email_bodies(
    *,
    briefing_markdown: str,
    fx_payload: dict,
    frontend_base_url: str,
    now_local: datetime,
    has_prioridad_alta: bool = False,
) -> tuple[str, str, str]:
    """Devuelve ``(subject, text, html)``: FX → Briefing → CTAs → disclaimer."""
    base = _normalize_base_url(frontend_base_url)
    terminal_url = f"{base}/terminal" if base else "/terminal"
    research_url = f"{base}/research" if base else "/research"

    fx_md = format_fx_ars_block(fx_payload)
    briefing = (briefing_markdown or "").strip()
    subject = build_email_subject(
        now_local=now_local,
        has_prioridad_alta=has_prioridad_alta,
    )

    text_plain = "\n".join(
        [
            fx_md,
            "",
            briefing,
            "",
            f"Abrir Terminal: {terminal_url}",
            f"Seguir en Research: {research_url}",
            "",
            _DISCLAIMER,
        ]
    ).strip() + "\n"

    html_body = "\n".join(
        [
            f'<div style="{_WRAPPER_STYLE}">',
            _fx_block_to_html(fx_payload),
            (
                _markdown_to_html(briefing, frontend_base_url=base)
                if briefing
                else ""
            ),
            f'<p style="{_CTA_STYLE}">'
            f'<a href="{html.escape(terminal_url, quote=True)}" style="{_BTN_STYLE}">'
            "Abrir Terminal</a>"
            f'<a href="{html.escape(research_url, quote=True)}" style="{_BTN_STYLE}">'
            "Seguir en Research</a>"
            "</p>",
            f'<p style="{_MUTED_STYLE}">{html.escape(_DISCLAIMER)}</p>',
            "</div>",
        ]
    )

    return subject, text_plain, html_body


if __name__ == "__main__":
    from datetime import timezone

    sample_fx = {
        "scope": "ars_usd",
        "source": "dolarapi.com",
        "fetched_at": "2026-07-23T11:00:00+00:00",
        "quotes": [
            {"label": "oficial", "bid": 1000, "ask": 1050},
            {"label": "blue", "bid": 1200, "ask": 1220},
            {"label": "mep", "bid": 1180, "ask": 1190},
        ],
    }
    now = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)

    messy = (
        "## Desde el último Briefing\n"
        "### Nuevo\n"
        "- El Ticker **TEST** cayó.\n"
        "### Sin cambio material\n"
        "- Nada.\n"
        "## Prioridad alta\n"
        "### TEST\n"
        "- Hecho: precio bajo.\n"
        "[Ver Dossier de TEST](dossier:TEST)\n"
    )
    subject, text, html_out = build_email_bodies(
        briefing_markdown=messy,
        fx_payload=sample_fx,
        frontend_base_url="https://myterm.solanodz.com/",
        now_local=now,
        has_prioridad_alta=True,
    )
    assert "## Desde" not in html_out
    assert "### Nuevo" not in html_out
    assert "<h2" in html_out and "<h3" in html_out
    assert "<ul" in html_out and "<li" in html_out
    assert "dossier?ticker=TEST" in html_out
    assert "myterm.solanodz.com/terminal" in html_out
    assert "<table" in html_out
    print("briefing_email_render self-check OK")
