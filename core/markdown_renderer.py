"""High-fidelity Markdown to HTML renderer for CAsk HUD.

Supports GitHub Flavored Markdown (tables, fenced code blocks, lists, math formulas)
with rich Catppuccin-inspired dark styling, preventing Qt md4c table/list parsing bugs.
"""

from __future__ import annotations

import html
import re

from core.math_formatter import format_math_in_markdown

CSS_THEME = """
<style>
body {
    color: #e6ebf5;
    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', 'Segoe UI', sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    margin: 0;
    padding: 0;
}
h1, h2, h3, h4, h5, h6 {
    color: #89b4fa;
    font-weight: 700;
    margin-top: 14px;
    margin-bottom: 6px;
}
h1 { font-size: 14pt; border-bottom: 1px solid rgba(255, 255, 255, 0.15); padding-bottom: 4px; }
h2 { font-size: 13pt; }
h3 { font-size: 12pt; }
p {
    margin-top: 6px;
    margin-bottom: 8px;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    border: 1px solid rgba(255, 255, 255, 0.18);
}
th {
    background-color: rgba(137, 180, 250, 0.18);
    color: #89b4fa;
    font-weight: bold;
    padding: 8px 12px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    text-align: left;
}
td {
    padding: 8px 12px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    vertical-align: top;
}
tr:nth-child(even) td {
    background-color: rgba(255, 255, 255, 0.03);
}
code {
    background-color: rgba(255, 255, 255, 0.08);
    color: #f9e2af;
    padding: 2px 5px;
    border-radius: 4px;
    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', monospace;
}
pre {
    background-color: rgba(18, 21, 26, 0.90);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 10px 14px;
    margin: 10px 0;
    color: #f9e2af;
    font-family: 'JetBrainsMono Nerd Font', 'JetBrains Mono', monospace;
    white-space: pre-wrap;
}
pre code {
    background: transparent;
    padding: 0;
    border: none;
}
blockquote {
    border-left: 3px solid #89b4fa;
    background-color: rgba(137, 180, 250, 0.08);
    margin: 8px 0;
    padding: 6px 12px;
    color: #cdd6f4;
}
ul, ol {
    margin: 6px 0;
    padding-left: 22px;
}
li {
    margin-bottom: 4px;
}
a {
    color: #89b4fa;
    text-decoration: underline;
}
hr {
    border: none;
    border-top: 1px solid rgba(255, 255, 255, 0.15);
    margin: 14px 0;
}
</style>
"""


def _fallback_render_markdown(text: str) -> str:
    """Built-in pure Python fallback parser for basic GFM markdown."""
    lines = text.splitlines()
    html_out = []
    in_code_block = False
    in_table = False
    in_ul = False
    in_ol = False
    code_lines = []
    table_rows = []

    def flush_list():
        nonlocal in_ul, in_ol
        if in_ul:
            html_out.append("</ul>")
            in_ul = False
        if in_ol:
            html_out.append("</ol>")
            in_ol = False

    def flush_table():
        nonlocal in_table, table_rows
        if not in_table or not table_rows:
            return
        html_out.append("<table>")
        is_header = True
        for row in table_rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            # Check if separator row like |:---|:---|
            if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                is_header = False
                continue
            tag = "th" if is_header else "td"
            row_html = "".join(f"<{tag}>{_format_inlines(c)}</{tag}>" for c in cells)
            html_out.append(f"<tr>{row_html}</tr>")
            is_header = False
        html_out.append("</table>")
        in_table = False
        table_rows = []

    def _format_inlines(s: str) -> str:
        s = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.*?)\*", r"<em>\1</em>", s)
        s = re.sub(r"`(.*?)`", r"<code>\1</code>", s)
        return s

    for line in lines:
        stripped = line.strip()

        # Fenced code block
        if stripped.startswith("```"):
            if in_code_block:
                escaped_code = html.escape("\n".join(code_lines))
                html_out.append(f"<pre><code>{escaped_code}</code></pre>")
                code_lines = []
                in_code_block = False
            else:
                flush_list()
                flush_table()
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Table row
        if stripped.startswith("|") and stripped.endswith("|"):
            flush_list()
            in_table = True
            table_rows.append(stripped)
            continue
        elif in_table:
            flush_table()

        # Headings
        if stripped.startswith("#"):
            flush_list()
            m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if m:
                level = len(m.group(1))
                html_out.append(f"<h{level}>{_format_inlines(m.group(2))}</h{level}>")
                continue

        # Blockquote
        if stripped.startswith(">"):
            flush_list()
            b_text = _format_inlines(stripped[1:].strip())
            html_out.append(f"<blockquote>{b_text}</blockquote>")
            continue

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            flush_list()
            html_out.append("<hr>")
            continue

        # Unordered list
        if re.match(r"^[-*•]\s+", stripped):
            if in_ol:
                flush_list()
            if not in_ul:
                html_out.append("<ul>")
                in_ul = True
            content = re.sub(r"^[-*•]\s+", "", stripped)
            html_out.append(f"<li>{_format_inlines(content)}</li>")
            continue

        # Ordered list
        m_ol = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m_ol:
            if in_ul:
                flush_list()
            if not in_ol:
                html_out.append("<ol>")
                in_ol = True
            html_out.append(f"<li>{_format_inlines(m_ol.group(2))}</li>")
            continue

        # Normal text / paragraph
        if stripped:
            flush_list()
            html_out.append(f"<p>{_format_inlines(stripped)}</p>")

    flush_list()
    flush_table()
    return "\n".join(html_out)


def render_markdown_to_html(content: str) -> str:
    """Render markdown text with math and GFM table support to modern dark HTML."""
    if not content:
        return f"{CSS_THEME}<body></body>"

    # Step 1: Pre-process LaTeX math formulas into clean Unicode representations
    formatted_math = format_math_in_markdown(content)

    # Step 2: Convert markdown to HTML (Python-Markdown with GFM extensions or fallback)
    body_html = ""
    try:
        import markdown
        body_html = markdown.markdown(
            formatted_math,
            extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
        )
    except Exception:
        body_html = _fallback_render_markdown(formatted_math)

    # Step 3: Wrap with CSS theme
    return f"{CSS_THEME}<body>{body_html}</body>"
