"""HTML email rendering.

Deliberately hand-rolled and old-fashioned: nested tables, inline styles, no
external CSS or images. Mail clients strip <style> blocks, ignore flexbox and
block remote assets, so anything more modern degrades into an unreadable wall
of text in exactly the clients that matter (Outlook, Gmail's clipper, iOS Mail).

Every message also carries a plain-text alternative built from the same data —
that is what a watch, a screen reader or a text-only client shows.
"""

from html import escape


CARD_BG = "#ffffff"
PAGE_BG = "#f1f5f9"
TEXT = "#0f172a"
MUTED = "#64748b"
BORDER = "#e2e8f0"
DEFAULT_BRAND = "#075985"


def _button(label: str, url: str, brand_color: str, *, primary: bool) -> str:
    """One add-to-calendar button, table-wrapped so Outlook renders the fill."""
    background = brand_color if primary else CARD_BG
    color = "#ffffff" if primary else TEXT
    border = brand_color if primary else BORDER
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="display:inline-block;margin:0 8px 8px 0;">'
        "<tr><td "
        f'style="background:{background};border:1px solid {border};border-radius:8px;">'
        f'<a href="{escape(url, quote=True)}" target="_blank" '
        f'style="display:inline-block;padding:11px 18px;font-family:Helvetica,Arial,sans-serif;'
        f'font-size:14px;font-weight:600;line-height:1;color:{color};text-decoration:none;">'
        f"{escape(label)}</a></td></tr></table>"
    )


def _detail_rows(rows: list[tuple[str, str]]) -> str:
    cells = []
    for label, value in rows:
        if not value:
            continue
        cells.append(
            '<tr>'
            f'<td style="padding:8px 0;font-family:Helvetica,Arial,sans-serif;font-size:13px;'
            f'color:{MUTED};white-space:nowrap;vertical-align:top;width:38%;">{escape(label)}</td>'
            f'<td style="padding:8px 0;font-family:Helvetica,Arial,sans-serif;font-size:14px;'
            f'color:{TEXT};font-weight:600;vertical-align:top;">{escape(value)}</td>'
            "</tr>"
        )
    if not cells:
        return ""
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="border-top:1px solid {BORDER};border-bottom:1px solid {BORDER};margin:20px 0;">'
        + "".join(cells)
        + "</table>"
    )


def _sections(sections: list[tuple[str, str]]) -> str:
    """Prose blocks: a heading and one or more paragraphs of running text."""
    blocks = []
    for heading, body in sections:
        if not (body or "").strip():
            continue
        paragraphs = "".join(
            f'<p style="margin:0 0 10px;font-family:Helvetica,Arial,sans-serif;font-size:14px;'
            f'line-height:1.6;color:{TEXT};">{escape(chunk.strip())}</p>'
            for chunk in body.strip().split("\n")
            if chunk.strip()
        )
        blocks.append(
            f'<div style="margin:22px 0 0;">'
            f'<h2 style="margin:0 0 8px;font-family:Helvetica,Arial,sans-serif;font-size:13px;'
            f'text-transform:uppercase;letter-spacing:.6px;color:{MUTED};">{escape(heading)}</h2>'
            f"{paragraphs}</div>"
        )
    return "".join(blocks)


def render_html(
    *,
    brand_name: str,
    brand_color: str,
    title: str,
    intro: str,
    rows: list[tuple[str, str]],
    sections: list[tuple[str, str]] | None = None,
    buttons: list[tuple[str, str]] | None = None,
    buttons_caption: str = "",
    note: str = "",
    footer: str = "",
) -> str:
    color = brand_color or DEFAULT_BRAND
    button_html = ""
    if buttons:
        rendered = "".join(
            _button(label, url, color, primary=index == 0) for index, (label, url) in enumerate(buttons)
        )
        caption = (
            f'<p style="margin:0 0 12px;font-family:Helvetica,Arial,sans-serif;font-size:13px;'
            f'color:{MUTED};">{escape(buttons_caption)}</p>'
            if buttons_caption
            else ""
        )
        button_html = f'<div style="margin:24px 0 4px;">{caption}{rendered}</div>'

    note_html = (
        f'<p style="margin:20px 0 0;padding:12px 14px;background:{PAGE_BG};border-radius:8px;'
        f'font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:1.5;color:{MUTED};">'
        f"{escape(note)}</p>"
        if note
        else ""
    )

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title></head>
<body style="margin:0;padding:0;background:{PAGE_BG};">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:{PAGE_BG};padding:28px 12px;">
<tr><td align="center">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;width:100%;background:{CARD_BG};border-radius:14px;overflow:hidden;border:1px solid {BORDER};">
<tr><td style="background:{color};padding:18px 28px;">
<span style="font-family:Helvetica,Arial,sans-serif;font-size:15px;font-weight:700;color:#ffffff;letter-spacing:.2px;">{escape(brand_name)}</span>
</td></tr>
<tr><td style="padding:28px;">
<h1 style="margin:0 0 12px;font-family:Helvetica,Arial,sans-serif;font-size:21px;line-height:1.3;color:{TEXT};">{escape(title)}</h1>
<p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:1.6;color:{TEXT};">{escape(intro)}</p>
{_detail_rows(rows)}
{_sections(sections or [])}
{button_html}
{note_html}
</td></tr>
<tr><td style="padding:16px 28px 24px;border-top:1px solid {BORDER};">
<p style="margin:0;font-family:Helvetica,Arial,sans-serif;font-size:12px;line-height:1.5;color:{MUTED};">{escape(footer)}</p>
</td></tr>
</table>
</td></tr></table>
</body></html>"""


def render_text(
    *,
    title: str,
    intro: str,
    rows: list[tuple[str, str]],
    sections: list[tuple[str, str]] | None = None,
    buttons: list[tuple[str, str]] | None = None,
    note: str = "",
    footer: str = "",
) -> str:
    lines = [title, "", intro, ""]
    lines += [f"{label}: {value}" for label, value in rows if value]
    for heading, body in sections or []:
        if body.strip():
            lines += ["", heading.upper(), body.strip()]
    if buttons:
        lines += ["", "Agregar a tu calendario:"]
        lines += [f"- {label}: {url}" for label, url in buttons]
    if note:
        lines += ["", note]
    if footer:
        lines += ["", "--", footer]
    return "\n".join(lines)
