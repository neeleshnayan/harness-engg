"""Render a daily archive memo to a shareable, letterhead-grade PDF.

    python scripts/archive_pdf.py docs/archives/2026-08-20.md

Writes docs/archives/2026-08-20.pdf next to the source. Zero dependencies:
the markdown is rendered to a print-styled HTML letter and pushed through
headless Chrome's print engine — the same proven path as the session's
earlier print work. Made for the secretary's §2 THE RECORD (2026-08-20,
CEO: "make the long record downloadable in pdf so we can share w executive
team"); §1 THE DAILY rides along at the top as the cover block.

Supported markdown (the secretary's formatting contract, nothing more):
#/##/### headings, pipe tables, bullet lists, **bold**, `code`, ---, and
plain paragraphs. Anything else renders as a paragraph rather than
breaking the letter.
"""

from __future__ import annotations

import html
import pathlib
import re
import subprocess
import sys
import tempfile

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

CSS = """
@page { size: A4; margin: 18mm 17mm 16mm; }
* { box-sizing: border-box; }
body { font-family: Georgia, 'Times New Roman', serif; color: #16181d;
       font-size: 10.2pt; line-height: 1.52; margin: 0; }
.masthead { border-bottom: 2.5px solid #16181d; padding-bottom: 8px;
            margin-bottom: 4px; display: flex; align-items: baseline;
            justify-content: space-between; }
.masthead .firm { font-family: 'Segoe UI', Arial, sans-serif;
                  font-weight: 700; font-size: 15pt;
                  letter-spacing: 0.14em; }
.masthead .doc { font-family: 'Segoe UI', Arial, sans-serif;
                 font-size: 8.2pt; letter-spacing: 0.22em;
                 text-transform: uppercase; color: #5a5f6a; }
.subrule { border-bottom: 0.75px solid #b9bdc6; margin-bottom: 18px;
           padding-bottom: 4px; font-family: 'Segoe UI', Arial, sans-serif;
           font-size: 8.2pt; color: #5a5f6a; letter-spacing: 0.08em; }
h1 { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13pt;
     letter-spacing: 0.02em; margin: 20px 0 8px; }
h2 { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.6pt;
     text-transform: uppercase; letter-spacing: 0.12em; color: #23262d;
     border-bottom: 0.75px solid #d5d8de; padding-bottom: 3px;
     margin: 22px 0 8px; page-break-after: avoid; }
h3 { font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.6pt;
     letter-spacing: 0.04em; margin: 14px 0 5px; page-break-after: avoid; }
p { margin: 0 0 7px; }
ul { margin: 0 0 8px 0; padding-left: 16px; }
li { margin-bottom: 3.5px; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 12px;
        font-size: 8.9pt; page-break-inside: avoid;
        font-variant-numeric: tabular-nums; }
th { font-family: 'Segoe UI', Arial, sans-serif; font-size: 7.8pt;
     text-transform: uppercase; letter-spacing: 0.09em; text-align: left;
     color: #5a5f6a; border-bottom: 1.25px solid #16181d;
     padding: 3px 10px 3px 0; }
td { border-bottom: 0.6px solid #e2e4e9; padding: 3.5px 10px 3.5px 0;
     vertical-align: top; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 8.6pt;
       background: #f1f2f5; padding: 0 3px; border-radius: 2px; }
hr { border: none; border-top: 0.75px solid #b9bdc6; margin: 16px 0; }
.footer { margin-top: 26px; border-top: 0.75px solid #b9bdc6;
          padding-top: 6px; font-family: 'Segoe UI', Arial, sans-serif;
          font-size: 7.6pt; color: #8a8f99; }
"""


def _inline(text: str) -> str:
    out = html.escape(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def md_to_html_body(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            close_list()
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and \
                re.match(r"^\|[\s\-|:]+\|$", lines[i + 1].strip()):
            close_list()
            headers = [c.strip() for c in s.strip("|").split("|")]
            out.append("<table><thead><tr>"
                       + "".join(f"<th>{_inline(h)}</th>" for h in headers)
                       + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>"
                                            for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        if s.startswith("### "):
            close_list()
            out.append(f"<h3>{_inline(s[4:])}</h3>")
        elif s.startswith("## "):
            close_list()
            out.append(f"<h2>{_inline(s[3:])}</h2>")
        elif s.startswith("# "):
            close_list()
            out.append(f"<h1>{_inline(s[2:])}</h1>")
        elif s.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(s[2:])}</li>")
        elif s in ("---", "***", "___"):
            close_list()
            out.append("<hr>")
        else:
            close_list()
            out.append(f"<p>{_inline(s)}</p>")
        i += 1
    close_list()
    return "\n".join(out)


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if pathlib.Path(c).exists():
            return c
    raise SystemExit("Chrome not found — the PDF path needs headless Chrome.")


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    md = src.read_text(encoding="utf-8")
    day = src.stem  # YYYY-MM-DD
    body = md_to_html_body(md)
    doc = (f"<!doctype html><html><head><meta charset='utf-8'>"
           f"<title>Krypton Fund — Daily Record {day}</title>"
           f"<style>{CSS}</style></head><body>"
           f"<div class='masthead'><span class='firm'>KRYPTON FUND</span>"
           f"<span class='doc'>Daily Record · {day}</span></div>"
           f"<div class='subrule'>Prepared by Donna, secretary · from the "
           f"event log, the flight recorder, and the day's commits · every "
           f"figure cited to the record</div>"
           f"{body}"
           f"<div class='footer'>Krypton Fund — internal daily record. "
           f"Paper venue; figures fold from the event log (NAV is never "
           f"broker equity). Generated by scripts/archive_pdf.py.</div>"
           f"</body></html>")
    with tempfile.TemporaryDirectory() as td:
        html_path = pathlib.Path(td) / f"{day}.html"
        html_path.write_text(doc, encoding="utf-8")
        pdf_path = src.with_suffix(".pdf")
        subprocess.run([
            find_chrome(), "--headless=new", "--disable-gpu",
            f"--print-to-pdf={pdf_path}", "--no-pdf-header-footer",
            str(html_path)], check=True, capture_output=True, timeout=120)
    print(f"wrote {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
