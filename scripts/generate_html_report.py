#!/usr/bin/env python3
"""
Generate a clean, standalone, single-file HTML report from a Markdown or JSON marketing intelligence digest.
Zero external CSS/JS dependencies — completely self-contained.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import html
import json
from pathlib import Path
import re
import sys


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0ea5e9;
      --action-border: #f59e0b;
      --action-badge: rgba(245, 158, 11, 0.15);
      --action-badge-text: #fbbf24;
      --signal-border: #3b82f6;
      --signal-badge: rgba(59, 130, 246, 0.15);
      --signal-badge-text: #60a5fa;
      --code-bg: #090d16;
      --table-header: #1e293b;
      --table-row-alt: #162032;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --bg: #f8fafc;
        --card-bg: #ffffff;
        --card-border: #e2e8f0;
        --text: #0f172a;
        --text-muted: #64748b;
        --accent: #0284c7;
        --accent-hover: #0369a1;
        --action-border: #d97706;
        --action-badge: #fef3c7;
        --action-badge-text: #b45309;
        --signal-border: #2563eb;
        --signal-badge: #dbeafe;
        --signal-badge-text: #1d4ed8;
        --code-bg: #f1f5f9;
        --table-header: #f1f5f9;
        --table-row-alt: #f8fafc;
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 2rem 1rem;
    }}
    .container {{
      max-width: 900px;
      margin: 0 auto;
    }}
    header {{
      border-bottom: 2px solid var(--card-border);
      padding-bottom: 1.5rem;
      margin-bottom: 2rem;
    }}
    h1 {{
      font-size: 2.25rem;
      font-weight: 700;
      color: var(--text);
      margin-bottom: 0.5rem;
    }}
    .meta {{
      display: flex;
      gap: 1rem;
      font-size: 0.875rem;
      color: var(--text-muted);
      flex-wrap: wrap;
    }}
    .badge {{
      display: inline-block;
      padding: 0.25rem 0.6rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .badge-action {{
      background: var(--action-badge);
      color: var(--action-badge-text);
      border: 1px solid var(--action-border);
    }}
    .badge-signal {{
      background: var(--signal-badge);
      color: var(--signal-badge-text);
      border: 1px solid var(--signal-border);
    }}
    h2 {{
      font-size: 1.5rem;
      margin-top: 2rem;
      margin-bottom: 1rem;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 0.4rem;
      color: var(--accent);
    }}
    h3 {{
      font-size: 1.2rem;
      margin-top: 1.5rem;
      margin-bottom: 0.5rem;
    }}
    p, ul, ol {{
      margin-bottom: 1rem;
    }}
    ul, ol {{
      padding-left: 1.5rem;
    }}
    li {{
      margin-bottom: 0.35rem;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 1.25rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    .card-action {{
      border-left: 4px solid var(--action-border);
    }}
    .card-signal {{
      border-left: 4px solid var(--signal-border);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1rem 0;
      font-size: 0.9rem;
    }}
    th, td {{
      padding: 0.75rem;
      text-align: left;
      border: 1px solid var(--card-border);
    }}
    th {{
      background-color: var(--table-header);
      font-weight: 600;
    }}
    tr:nth-child(even) {{
      background-color: var(--table-row-alt);
    }}
    code {{
      background-color: var(--code-bg);
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85em;
    }}
    pre {{
      background-color: var(--code-bg);
      padding: 1rem;
      border-radius: 6px;
      overflow-x: auto;
      margin-bottom: 1rem;
    }}
    pre code {{
      padding: 0;
      background: none;
    }}
    blockquote {{
      border-left: 4px solid var(--accent);
      padding-left: 1rem;
      margin: 1rem 0;
      color: var(--text-muted);
      font-style: italic;
    }}
    footer {{
      margin-top: 3rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--card-border);
      text-align: center;
      font-size: 0.8rem;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>{title}</h1>
      <div class="meta">
        <span>Generated: {date}</span>
        <span>Type: Marketing & Ecommerce Intelligence Digest</span>
        <span>Format: Standalone Offline Report</span>
      </div>
    </header>
    <main>
      {content}
    </main>
    <footer>
      Mellanni Marketing Intelligence &bull; Standalone Agent Deliverable
    </footer>
  </div>
</body>
</html>
"""


def markdown_to_html_simple(md_text: str) -> str:
    """Convert basic Markdown to clean HTML without external dependencies."""
    lines = md_text.splitlines()
    html_lines: list[str] = []
    in_list = False
    in_code_block = False
    code_block_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Code blocks
        if stripped.startswith("```"):
            if in_code_block:
                in_code_block = False
                escaped_code = html.escape("\n".join(code_block_lines))
                html_lines.append(f"<pre><code>{escaped_code}</code></pre>")
                code_block_lines = []
            else:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                in_code_block = True
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Blank line
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        # Headers
        if stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            text = format_inline(stripped[4:])
            html_lines.append(f"<h3>{text}</h3>")
        elif stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            text = format_inline(stripped[3:])
            html_lines.append(f"<h2>{text}</h2>")
        elif stripped.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            text = format_inline(stripped[2:])
            html_lines.append(f"<h1>{text}</h1>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            text = format_inline(stripped[2:])
            html_lines.append(f"<li>{text}</li>")
        elif stripped.startswith("> "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            text = format_inline(stripped[2:])
            html_lines.append(f"<blockquote>{text}</blockquote>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            text = format_inline(line)
            html_lines.append(f"<p>{text}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def format_inline(text: str) -> str:
    """Format inline markdown elements: links, bold, italics, code, badges."""
    # Escape HTML first
    text = html.escape(text)

    # Convert badges
    text = re.sub(r'\[ACTION\]', '<span class="badge badge-action">Action</span>', text, flags=re.IGNORECASE)
    text = re.sub(r'\[SIGNAL\]', '<span class="badge badge-signal">Signal</span>', text, flags=re.IGNORECASE)

    # Inline code: `code`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Bold: **text**
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)

    # Italic: *text*
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)

    # Links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', text)

    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Markdown intelligence digest to standalone HTML")
    parser.add_argument("input", type=Path, help="Input Markdown (.md) or JSON file")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output HTML file path (default: <input>.html)")
    parser.add_argument("--title", type=str, default="Mellanni Marketing Intelligence Digest", help="Report Title")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    content_raw = args.input.read_text(encoding="utf-8")
    
    if args.input.suffix.lower() == ".json":
        try:
            data = json.loads(content_raw)
            title = data.get("title", args.title)
            body = data.get("body", "")
            if isinstance(body, dict):
                body_md = json.dumps(body, indent=2)
            else:
                body_md = str(body)
            html_content = markdown_to_html_simple(body_md)
        except json.JSONDecodeError:
            print("Error: Invalid JSON input", file=sys.stderr)
            return 1
    else:
        title = args.title
        first_line = content_raw.strip().splitlines()[0] if content_raw.strip() else ""
        if first_line.startswith("# "):
            title = first_line[2:].strip()
        html_content = markdown_to_html_simple(content_raw)

    rendered = HTML_TEMPLATE.format(
        title=html.escape(title),
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        content=html_content,
    )

    output_path = args.output or args.input.with_suffix(".html")
    output_path.write_text(rendered, encoding="utf-8")
    print(f"Standalone HTML report generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
