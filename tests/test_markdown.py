from app.markdown import render_block, render_inline


def test_inline_renders_code_and_bold():
    assert str(render_inline("use `stop_reason` and **stop**")) == (
        "use <code>stop_reason</code> and <strong>stop</strong>"
    )


def test_inline_escapes_html():
    assert "<script>" not in str(render_inline("<script>alert(1)</script>"))


def test_inline_handles_empty_input():
    assert str(render_inline("")) == ""


def test_block_renders_paragraph_and_bullets():
    html = str(render_block("Head text.\n- A: wrong.\n- B: also wrong."))
    assert html == "<p>Head text.</p><ul><li>A: wrong.</li><li>B: also wrong.</li></ul>"


def test_block_separates_paragraphs():
    html = str(render_block("First.\n\nSecond."))
    assert html == "<p>First.</p><p>Second.</p>"


def test_block_supports_bullets_before_text():
    html = str(render_block("- one\ntail"))
    assert html == "<ul><li>one</li></ul><p>tail</p>"


def test_block_escapes_html_inside_bullets():
    html = str(render_block("- <b>bold</b>"))
    assert "<b>" not in html
    assert "&lt;b&gt;" in html
