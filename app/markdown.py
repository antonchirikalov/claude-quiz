"""A deliberately tiny Markdown subset for question text and explanations.

The question banks are authored as Markdown: explanations are a paragraph plus a
bullet per distractor, and stems use `inline code` and **bold**. Rendering that
subset here keeps the app dependency-free — no full Markdown engine needed.
"""

import re

from markupsafe import Markup, escape

_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def render_inline(text: str) -> Markup:
    """Escape HTML, then render `code` and **bold**. No block elements."""
    out = str(escape(text or ""))
    out = _CODE.sub(r"<code>\1</code>", out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    return Markup(out)


def render_block(text: str) -> Markup:
    """Render paragraphs and '- ' bullet lists on top of render_inline()."""
    html: list[str] = []
    bullets: list[str] = []

    def flush_bullets() -> None:
        if bullets:
            items = "".join(f"<li>{b}</li>" for b in bullets)
            html.append(f"<ul>{items}</ul>")
            bullets.clear()

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            flush_bullets()
            continue
        if line.startswith(("- ", "* ")):
            bullets.append(str(render_inline(line[2:])))
        else:
            flush_bullets()
            html.append(f"<p>{render_inline(line)}</p>")

    flush_bullets()
    return Markup("".join(html))
