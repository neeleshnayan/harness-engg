# -*- coding: utf-8 -*-
"""THE LIBRARY RENDERER — markdown research notes -> house-styled PDF.

Design language: the Entry-20 one-pager (CEO-approved 2026-08-22/23):
Georgia serif display, green kicker, uppercase meta labels, clean ruled
tables. Renders via headless Chrome --print-to-pdf.

Usage: python scripts/library/render_note.py <input.md> [output.pdf]
Default output: data/library/<input-stem>.pdf
"""
import html
import pathlib
import re
import subprocess
import sys
import tempfile

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
  @page { size: A4; margin: 14mm 15mm 16mm 15mm; }
  body { font-family: "Segoe UI", -apple-system, sans-serif; font-size: 9.2pt;
         line-height: 1.5; color: #1A1917; margin: 0; }
  .firm { font-family: Georgia, serif; font-weight: bold; font-size: 11pt; letter-spacing: .03em; }
  .meta { font-size: 7pt; color: #6B675F; text-transform: uppercase; letter-spacing: .1em; }
  .kicker { font-size: 7.4pt; text-transform: uppercase; letter-spacing: .13em; color: #1E6B4F;
            font-weight: 600; margin: 14pt 0 4pt; }
  h1 { font-family: Georgia, serif; font-weight: 500; font-size: 20pt; margin: 2pt 0 6pt; line-height: 1.14; }
  h2 { font-family: Georgia, serif; font-weight: 600; font-size: 12.5pt; margin: 14pt 0 5pt;
       padding-bottom: 2pt; border-bottom: 1.2pt solid #1A1917; }
  h3 { font-size: 9.6pt; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
       color: #3D3A34; margin: 11pt 0 4pt; }
  p { margin: 0 0 6pt; }
  ul, ol { margin: 0 0 7pt 16pt; padding: 0; }
  li { margin-bottom: 2.5pt; }
  b, strong { color: #14120F; }
  table { border-collapse: collapse; width: 100%; margin: 6pt 0 9pt; font-size: 8.3pt; }
  th { text-align: left; font-size: 7.2pt; text-transform: uppercase; letter-spacing: .07em;
       color: #6B675F; border-bottom: 1.1pt solid #1A1917; padding: 3pt 7pt 3pt 0; }
  td { border-bottom: 0.5pt solid #DDD9D1; padding: 3.5pt 7pt 3.5pt 0; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  code, pre { font-family: Consolas, monospace; font-size: 8.1pt; }
  pre { background: #F5F3EE; border-left: 2.2pt solid #1E6B4F; padding: 7pt 9pt; margin: 6pt 0 9pt;
        white-space: pre-wrap; }
  blockquote { border-left: 2.2pt solid #B8B2A6; margin: 6pt 0 8pt; padding: 2pt 0 2pt 10pt;
               color: #4A463F; font-style: italic; }
  .rule { border: none; border-top: 0.6pt solid #B8B2A6; margin: 12pt 0; }
  .footer { margin-top: 16pt; padding-top: 6pt; border-top: 0.6pt solid #B8B2A6;
            font-size: 6.8pt; color: #6B675F; text-transform: uppercase; letter-spacing: .09em; }
"""


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<b>\1</b>", s)  # links render as bold text in print
    return s


def md_to_html(md: str):
    lines = md.replace("\r\n", "\n").split("\n")
    out, i, title = [], 0, None
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            out.append("<pre>" + html.escape("\n".join(block)) + "</pre>")
            i += 1
            continue
        if re.match(r"^\s*---+\s*$", ln):
            out.append('<hr class="rule">')
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", ln)
        if m:
            lvl, text = len(m.group(1)), m.group(2).strip()
            if lvl == 1 and title is None:
                title = re.sub(r"[*`_]", "", text)
                out.append("<h1>" + inline(text) + "</h1>")
            else:
                out.append(f"<h{min(lvl,3)}>" + inline(text) + f"</h{min(lvl,3)}>")
            i += 1
            continue
        if "|" in ln and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            hdr = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows, i2 = [], i + 2
            while i2 < len(lines) and "|" in lines[i2] and lines[i2].strip():
                rows.append([c.strip() for c in lines[i2].strip().strip("|").split("|")])
                i2 += 1
            t = ["<table><tr>" + "".join(f"<th>{inline(h)}</th>" for h in hdr) + "</tr>"]
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</table>")
            out.append("".join(t))
            i = i2
            continue
        if re.match(r"^\s*[-*]\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                item = re.sub(r"^\s*[-*]\s+", "", lines[i])
                while i + 1 < len(lines) and lines[i + 1].startswith("  ") and not re.match(r"^\s*[-*]\s+", lines[i + 1]):
                    i += 1
                    item += " " + lines[i].strip()
                items.append("<li>" + inline(item) + "</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if re.match(r"^\s*\d+\.\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                item = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                while i + 1 < len(lines) and lines[i + 1].startswith("  ") and not re.match(r"^\s*(\d+\.|[-*])\s+", lines[i + 1]):
                    i += 1
                    item += " " + lines[i].strip()
                items.append("<li>" + inline(item) + "</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        if ln.strip().startswith(">"):
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + inline(" ".join(q)) + "</blockquote>")
            continue
        if ln.strip():
            para = [ln.strip()]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(
                r"^(\s*[-*]\s+|\s*\d+\.\s+|#{1,3}\s|```|\s*---+\s*$|\s*>|.*\|)", lines[i + 1]
            ):
                i += 1
                para.append(lines[i].strip())
            out.append("<p>" + inline(" ".join(para)) + "</p>")
        i += 1
    return "\n".join(out), (title or "Research Note")


def render(md_path: pathlib.Path, out_pdf: pathlib.Path) -> None:
    body, title = md_to_html(md_path.read_text(encoding="utf-8"))
    from datetime import date

    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<table style="margin:0 0 2pt"><tr>
<td style="border:none;padding:0"><span class="firm">KRYPTON FUND</span></td>
<td style="border:none;padding:0;text-align:right"><span class="meta">Research Library · {date.today().isoformat()}</span></td>
</tr></table>
<div class="kicker">Reading / Research Note</div>
{body}
<div class="footer">Krypton Fund · internal research · rendered from {html.escape(md_path.name)} · the primary record is the flight recorder</div>
</body></html>"""
    chrome = next((c for c in CHROME_CANDIDATES if pathlib.Path(c).exists()), None)
    if not chrome:
        raise SystemExit("no Chrome/Edge found for print-to-pdf")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
        tmp = f.name
    out_pdf = out_pdf.resolve()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", f"--print-to-pdf={out_pdf}", "--no-pdf-header-footer", tmp],
        check=True, capture_output=True, timeout=120,
    )
    pathlib.Path(tmp).unlink(missing_ok=True)
    print(f"wrote {out_pdf} ({out_pdf.stat().st_size} bytes) - {title}")


if __name__ == "__main__":
    src = pathlib.Path(sys.argv[1])
    dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path("data/library") / (src.stem + ".pdf")
    render(src, dst)
