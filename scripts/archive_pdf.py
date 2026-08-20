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

# Design (2026-08-20, CEO: "more badass... theme color and great
# aesthetics... Jony Ive"): ONE accent — the fund's emerald, deepened for
# ink (#0B6B4D on paper, #2FBF8F on the cover's near-black); a full-bleed
# ink cover band; oversized roman section numerals as the editorial
# signature; everything else reduced to hairlines and space. Loud in
# exactly one place, silent everywhere else.
INK = "#0E1215"
PAPER = "#FFFFFF"
ACCENT = "#0DA271"         # live emerald on paper (v2's evergreen read flat)
ACCENT_BRIGHT = "#3FE0A5"  # emerald on the ink band
MUTED = "#707680"
HAIR = "#DCE0E4"

CSS = f"""
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box;
     -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{ font-family: Georgia, 'Times New Roman', serif; color: {INK};
        background: {PAPER}; font-size: 10.2pt; line-height: 1.55;
        margin: 0; padding: 0 20mm 16mm; }}
.cover {{ margin: 0 -20mm 8mm; background: {INK}; color: #F4F6F5;
          padding: 10mm 20mm 7mm; border-bottom: 3px solid {ACCENT}; }}
.cover .firm {{ font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 700; font-size: 19pt;
                letter-spacing: 0.22em; }}
.cover .firm .k {{ color: {ACCENT_BRIGHT}; }}
.cover .doc {{ font-family: 'Segoe UI', Arial, sans-serif;
               font-size: 8.4pt; letter-spacing: 0.34em;
               text-transform: uppercase; color: {ACCENT_BRIGHT};
               margin-top: 5px; }}
.cover .prepared {{ font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 7.4pt; letter-spacing: 0.06em;
                    color: #9AA2A9; margin-top: 7px; }}
h1 {{ font-family: 'Segoe UI', Arial, sans-serif; font-weight: 650;
      font-size: 13.5pt; letter-spacing: 0.06em; margin: 12px 0 8px;
      text-transform: uppercase; }}
/* The lede — the book line that opens THE DAILY — carries the page. */
h1 + p {{ font-size: 11.6pt; line-height: 1.6; padding-left: 12px;
          border-left: 3px solid {ACCENT}; margin: 0 0 11px; }}
h2 {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 24px 0 9px;
      display: flex; align-items: baseline; gap: 10px;
      border-bottom: 0.75px solid {HAIR}; padding-bottom: 5px;
      page-break-after: avoid; }}
h2 .num {{ font-weight: 300; font-size: 19pt; color: {ACCENT};
           min-width: 26px; line-height: 1; letter-spacing: 0.02em; }}
h2 .t {{ font-size: 10.4pt; text-transform: uppercase;
         letter-spacing: 0.15em; color: {INK}; font-weight: 650; }}
h3 {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 9.6pt;
      letter-spacing: 0.04em; margin: 14px 0 5px;
      page-break-after: avoid; }}
p {{ margin: 0 0 7px; }}
ul {{ margin: 0 0 9px 0; padding-left: 15px; list-style: none; }}
li {{ margin-bottom: 4px; position: relative; }}
li::before {{ content: ""; position: absolute; left: -15px; top: 0.62em;
              width: 8px; height: 2px; background: {ACCENT}; }}
table {{ border-collapse: collapse; width: 100%; margin: 7px 0 13px;
         font-size: 8.9pt; page-break-inside: avoid;
         font-family: 'Segoe UI', Arial, sans-serif;
         font-variant-numeric: tabular-nums; }}
th {{ font-size: 7.6pt; text-transform: uppercase;
      letter-spacing: 0.11em; text-align: left; color: {MUTED};
      border-bottom: 1.5px solid {ACCENT}; padding: 3px 10px 4px 0; }}
td {{ border-bottom: 0.6px solid {HAIR}; padding: 4.5px 10px 4.5px 0;
      vertical-align: top; }}
tr td:first-child {{ font-weight: 600; }}
code {{ font-family: Consolas, 'Courier New', monospace; font-size: 8.6pt;
        background: #F0F3F2; color: {ACCENT}; padding: 0 3px;
        border-radius: 2px; }}
b {{ letter-spacing: 0.005em; }}
hr {{ border: none; border-top: 0.75px solid {HAIR}; margin: 16px 0; }}
.footer {{ margin-top: 18px; border-top: 2px solid {INK};
           padding-top: 6px; font-family: 'Segoe UI', Arial, sans-serif;
           font-size: 7.4pt; color: {MUTED}; letter-spacing: 0.04em;
           display: flex; justify-content: space-between; }}
.footer .mark {{ color: {ACCENT}; font-weight: 700;
                 letter-spacing: 0.18em; }}
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
        if s.startswith("# "):
            close_list()
            # The letterhead carries the firm's name; an H1 repeating it is
            # noise (CEO, 2026-08-20). Strip a leading "KRYPTON FUND — "
            # defensively so the page says the name exactly once.
            h1 = re.sub(r"^KRYPTON\s+FUND\s*[—-]\s*", "", s[2:], flags=re.I)
            out.append(f"<h1>{_inline(h1)}</h1>")
        elif s.startswith("### "):
            close_list()
            out.append(f"<h3>{_inline(s[4:])}</h3>")
        elif s.startswith("## "):
            close_list()
            # "II. Trading & execution" -> oversized roman numeral + tracked
            # caps title: the letter's editorial signature.
            m = re.match(r"^([IVXLC]+)\.\s+(.*)$", s[3:])
            if m:
                out.append(f"<h2><span class='num'>{m.group(1)}</span>"
                           f"<span class='t'>{_inline(m.group(2))}</span></h2>")
            else:
                out.append(f"<h2><span class='t'>{_inline(s[3:])}</span></h2>")
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
           f"<div class='cover'>"
           f"<div class='firm'><span class='k'>K</span>RYPTON FUND</div>"
           f"<div class='doc'>The Daily Record &nbsp;·&nbsp; {day}</div>"
           f"<div class='prepared'>Prepared by Donna, secretary — from the "
           f"event log, the flight recorder, and the day's commits. Every "
           f"figure cited to the record.</div>"
           f"</div>"
           f"{body}"
           f"<div class='footer'><span class='mark'>K</span>"
           f"<span>Internal daily record · paper venue · figures fold from "
           f"the event log; NAV is never broker equity"
           f"</span><span>{day}</span></div>"
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
