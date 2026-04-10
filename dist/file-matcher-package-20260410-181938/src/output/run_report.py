"""HTML summary after a CLI run: links table + open in Excel / Google Sheets."""

from __future__ import annotations

import html
from pathlib import Path


def write_run_report(
    report_path: str | Path,
    xlsx_path: str | Path,
    link_rows: list[tuple[int, str, str]],
) -> Path:
    """Write HTML next to the workbook. link_rows: (ledger_row, filename, url)."""
    report_path = Path(report_path)
    xlsx_path = Path(xlsx_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    xlsx_name = html.escape(xlsx_path.name)
    # Same directory: relative link works when opening the HTML file locally.
    xlsx_href = html.escape(xlsx_path.name)

    rows_html = []
    for idx, fname, url in link_rows:
        if not url:
            continue
        esc_url = html.escape(url, quote=True)
        rows_html.append(
            "<tr>"
            f"<td class='num'>{idx}</td>"
            f"<td class='mono'>{html.escape(fname)}</td>"
            f'<td class="mono"><a href="{esc_url}">{html.escape(url)}</a></td>'
            "</tr>"
        )
    table_body = "\n".join(rows_html) if rows_html else "<tr><td colspan='3'>No file links</td></tr>"

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>File Manager — run report</title>
  <style>
    :root {{
      font-family: system-ui, sans-serif;
      background: #faf9f5;
      color: #1a1a1a;
    }}
    body {{ max-width: 960px; margin: 2rem auto; padding: 0 1.25rem; }}
    h1 {{ font-size: 1.35rem; margin-bottom: 0.35rem; }}
    .muted {{ color: #555; font-size: 0.9rem; margin-bottom: 1.25rem; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1.25rem 0 1.5rem; }}
    .btn {{
      display: inline-block;
      padding: 0.55rem 1.1rem;
      border-radius: 0.5rem;
      font-weight: 600;
      font-size: 0.9rem;
      text-decoration: none;
      border: 1px solid #c4c2b8;
      background: #fff;
      color: #0f3d2e;
      box-shadow: 0 1px 2px rgba(0,0,0,0.06);
    }}
    .btn:hover {{ background: #f0efe8; }}
    .btn-primary {{ background: #0f3d2e; color: #fff; border-color: #0f3d2e; }}
    .btn-primary:hover {{ background: #164732; }}
    .hint {{ font-size: 0.82rem; color: #555; max-width: 42rem; line-height: 1.45; }}
    h2 {{ font-size: 1rem; margin-top: 1.75rem; margin-bottom: 0.5rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; background: #fff;
      border: 1px solid #e5e3da; border-radius: 0.5rem; overflow: hidden; }}
    th, td {{ text-align: left; padding: 0.45rem 0.55rem; border-bottom: 1px solid #eee; vertical-align: top; }}
    th {{ background: #f4f3ed; font-weight: 600; }}
    tr:last-child td {{ border-bottom: none; }}
    .num {{ width: 3rem; white-space: nowrap; }}
    .mono {{ font-family: ui-monospace, monospace; word-break: break-all; }}
    td a {{ color: #0b57d0; }}
  </style>
</head>
<body>
  <h1>Matching run complete</h1>
  <p class="muted">Workbook: <strong>{xlsx_name}</strong> (same folder as this report)</p>
  <div class="actions">
    <a class="btn btn-primary" href="{xlsx_href}">Open with Excel</a>
    <a class="btn" href="https://sheet.new" target="_blank" rel="noopener">Open in Google Sheets</a>
  </div>
  <p class="hint">
    <strong>Google Sheets:</strong> A new spreadsheet opens in another tab. Use <em>File → Import → Upload</em>
    and choose <strong>{xlsx_name}</strong> from this folder (or drag the file into the sheet).
  </p>
  <h2>Matched file links</h2>
  <table>
    <thead><tr><th>Row</th><th>File</th><th>Link</th></tr></thead>
    <tbody>
    {table_body}
    </tbody>
  </table>
</body>
</html>
"""
    report_path.write_text(doc, encoding="utf-8")
    return report_path
