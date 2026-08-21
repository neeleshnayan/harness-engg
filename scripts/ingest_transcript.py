"""Lift a session task JSONL into `fund_agent_transcripts`.

The CEO's decision, 2026-08-21: the INTERACTION behind a run must outlive the
session. `fund_agent_runs.output` holds what a seat concluded; the brief it was
given and the turns it took to get there live in a `.jsonl` that is a session
artifact and nothing else's business.

THE SHAPE IS MEASURED, NOT ASSUMED. Read off a real 53 MB / 21,466-line session
file on 2026-08-21:

    type       user 4978 · assistant 8861 · system 310 · attachment 3013 · ...
    message.role  user | assistant   (absent on non-message lines)
    user content    a STRING, or a list of blocks
    assistant content  a LIST of blocks: thinking | text | tool_use | tool_result
    isSidechain: true  marks SUB-AGENT turns — a seat's dispatch is a sidechain

That last field is the one that makes this script possible: a dispatch to the
builder, the pm or the quant runs as a sidechain inside the CTO's session, so
`--sidechain-only` (the default) extracts exactly that seat's own conversation
and nothing of the chair's.

WHAT IT WILL NOT DO:
  * it does not write to `.claude/` — it reads a session file and POSTs to the
    spine, nothing else;
  * it does not TRUNCATE. Over the budget it REFUSES and tells you which knob
    to turn. A transcript silently cut in half is a transcript that lies about
    what was said, and this table exists precisely so nobody has to trust a
    summary;
  * it does not guess at an unrecognised shape. Zero extractable turns is an
    error with the line-type census printed, not an empty upload.

Usage:
    python scripts/ingest_transcript.py --jsonl <path> --run-id run-builder-7
    ... --kind transcript        brief | report | transcript  (default transcript)
    ... --dry-run                print to stdout, POST nothing
    ... --include-thinking       keep assistant reasoning blocks (off by default)
    ... --all-turns              include the main session, not just the sidechain
    ... --max-chars 400000       the refusal budget
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

BASE = "http://127.0.0.1:8090/api/v1/fund"

#: Refuse above this many characters. ~400k chars is roughly 100k tokens — far
#: more than any single dispatch has produced, and small enough that a runaway
#: file is caught before it becomes a row nobody can read.
DEFAULT_MAX_CHARS = 400_000


def _lines(path: Path) -> Iterator[dict[str, Any]]:
    """Stream the file. It is tens of megabytes; reading it whole is not free."""
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError:
                yield {"type": "UNPARSEABLE"}


def _text_of(content: Any, include_thinking: bool) -> str:
    """Flatten one message's content to text, naming what it drops.

    A tool call becomes a one-line marker rather than its full input: the
    arguments are often a whole file, and a transcript that inlined them would
    be mostly payload. The marker keeps the SHAPE of the conversation — which is
    what a later reader is here for — and says a call happened.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for b in content:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text":
            parts.append(str(b.get("text") or ""))
        elif t == "thinking" and include_thinking:
            parts.append("[thinking]\n" + str(b.get("thinking") or ""))
        elif t == "tool_use":
            parts.append(f"[tool_use: {b.get('name')}]")
        elif t == "tool_result":
            # Results are frequently enormous (a file read, a test log). The
            # marker records that one came back and how big it was.
            body = b.get("content")
            size = len(json.dumps(body, default=str)) if body is not None else 0
            parts.append(f"[tool_result: {size} chars]")
    return "\n".join(p for p in parts if p.strip())


def extract(path: Path, *, sidechain_only: bool, include_thinking: bool,
            session: str | None = None) -> dict[str, Any]:
    """Turns, in order, plus a census of every line type seen."""
    census: Counter[str] = Counter()
    turns: list[str] = []
    kept_sidechain = 0
    for o in _lines(path):
        census[str(o.get("type"))] += 1
        if session and o.get("sessionId") != session:
            continue
        msg = o.get("message")
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        is_side = bool(o.get("isSidechain"))
        if sidechain_only and not is_side:
            continue
        if is_side:
            kept_sidechain += 1
        text = _text_of(msg.get("content"), include_thinking)
        if not text.strip():
            continue
        ts = str(o.get("timestamp") or "")[:19].replace("T", " ")
        turns.append(f"--- {role} {ts} ---\n{text}")
    return {
        "turns": turns,
        "census": dict(census),
        "sidechain_turns": kept_sidechain,
        "content": "\n\n".join(turns),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jsonl", required=True, type=Path)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--kind", default="transcript",
                    choices=("brief", "report", "transcript"))
    ap.add_argument("--session", default=None,
                    help="only lines from this sessionId")
    ap.add_argument("--all-turns", action="store_true",
                    help="include the main session, not only the sidechain")
    ap.add_argument("--include-thinking", action="store_true")
    ap.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--base", default=BASE)
    a = ap.parse_args(argv)

    if not a.jsonl.exists():
        print(f"no such file: {a.jsonl}", file=sys.stderr)
        return 2

    got = extract(a.jsonl, sidechain_only=not a.all_turns,
                  include_thinking=a.include_thinking, session=a.session)
    content = got["content"]

    if not content.strip():
        # An empty upload would read as "we captured this run" when nothing was
        # captured. Refuse, and print what WAS in the file so the caller can see
        # whether they picked the wrong file or the wrong filter.
        print("REFUSED: no extractable turns.", file=sys.stderr)
        print(f"  line types seen: {got['census']}", file=sys.stderr)
        print("  if this dispatch was not a sub-agent, re-run with --all-turns",
              file=sys.stderr)
        return 1

    if len(content) > a.max_chars:
        # REFUSE, never truncate. A transcript cut in half lies about what was
        # said, and this table exists so nobody has to trust a summary.
        print(f"REFUSED: {len(content):,} chars exceeds the {a.max_chars:,} budget.",
              file=sys.stderr)
        print(f"  {len(got['turns'])} turns extracted. Narrow with --session, "
              f"or raise --max-chars deliberately.", file=sys.stderr)
        return 1

    if a.dry_run:
        print(content)
        print(f"\n[dry run] {len(got['turns'])} turns, {len(content):,} chars, "
              f"would POST kind={a.kind} to run {a.run_id}", file=sys.stderr)
        return 0

    body = json.dumps({"kind": a.kind, "content": content,
                       "meta": {"source": a.jsonl.name,
                                "turns": len(got["turns"]),
                                "sidechain_only": not a.all_turns,
                                "include_thinking": a.include_thinking}}).encode()
    req = urllib.request.Request(
        f"{a.base}/desk/runs/{a.run_id}/transcript", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            print(json.dumps(json.load(r), indent=1))
    except urllib.error.HTTPError as e:
        print(f"POST failed {e.code}: {e.read().decode()[:400]}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"POST failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
