"""Lifting a session JSONL into the transcripts table.

Shapes measured off a real 53 MB / 21,466-line session file on 2026-08-21, not
assumed — see the module docstring in scripts/ingest_transcript.py for the
census. The two behaviours worth guarding:

  * it REFUSES rather than truncating. A transcript cut in half lies about what
    was said, and the table exists so nobody has to trust a summary;
  * it REFUSES rather than uploading nothing. An empty row reads as "we captured
    this run" when the caller picked the wrong file or the wrong filter, so the
    refusal prints the line-type census and names the knob.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ingest_transcript import extract, main  # noqa: E402


def _jsonl(tmp_path, rows):
    p = tmp_path / "session.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def _msg(role, content, side=False, ts="2026-08-21T09:00:00.000Z", **kw):
    return {"type": role, "isSidechain": side, "timestamp": ts,
            "sessionId": kw.pop("session", "s1"),
            "message": {"role": role, "content": content}, **kw}


def test_a_user_string_and_an_assistant_block_list_both_extract(tmp_path):
    p = _jsonl(tmp_path, [
        _msg("user", "do the thing", side=True),
        _msg("assistant", [{"type": "text", "text": "did it"}], side=True),
    ])
    got = extract(p, sidechain_only=True, include_thinking=False)
    assert len(got["turns"]) == 2
    assert "do the thing" in got["content"]
    assert "did it" in got["content"]


def test_only_the_SIDECHAIN_is_taken_by_default(tmp_path):
    """A seat's dispatch runs as a sidechain inside the chair's session. The
    default must not sweep up the CTO's own conversation."""
    p = _jsonl(tmp_path, [
        _msg("user", "chair talking", side=False),
        _msg("user", "seat talking", side=True),
    ])
    got = extract(p, sidechain_only=True, include_thinking=False)
    assert "seat talking" in got["content"]
    assert "chair talking" not in got["content"]
    assert got["sidechain_turns"] == 1


def test_all_turns_takes_the_main_session_too(tmp_path):
    p = _jsonl(tmp_path, [
        _msg("user", "chair talking", side=False),
        _msg("user", "seat talking", side=True),
    ])
    got = extract(p, sidechain_only=False, include_thinking=False)
    assert "chair talking" in got["content"] and "seat talking" in got["content"]


def test_thinking_is_EXCLUDED_unless_asked_for(tmp_path):
    p = _jsonl(tmp_path, [_msg("assistant", [
        {"type": "thinking", "thinking": "private reasoning"},
        {"type": "text", "text": "public answer"},
    ], side=True)])
    off = extract(p, sidechain_only=True, include_thinking=False)["content"]
    on = extract(p, sidechain_only=True, include_thinking=True)["content"]
    assert "private reasoning" not in off
    assert "public answer" in off
    assert "private reasoning" in on


def test_a_tool_call_becomes_a_MARKER_not_its_whole_payload(tmp_path):
    """Arguments are frequently a whole file. The marker keeps the SHAPE of the
    conversation, which is what a later reader is here for."""
    p = _jsonl(tmp_path, [_msg("assistant", [
        {"type": "tool_use", "name": "Edit", "input": {"content": "x" * 10_000}},
        {"type": "tool_result", "content": "y" * 5_000},
    ], side=True)])
    c = extract(p, sidechain_only=True, include_thinking=False)["content"]
    assert "[tool_use: Edit]" in c
    assert "tool_result" in c
    assert "x" * 100 not in c, "the tool input was inlined"
    assert len(c) < 500


def test_a_census_of_every_line_type_is_returned(tmp_path):
    p = _jsonl(tmp_path, [
        _msg("user", "a", side=True),
        {"type": "attachment", "attachment": {}},
        {"type": "mode", "mode": "x"},
    ])
    got = extract(p, sidechain_only=True, include_thinking=False)
    assert got["census"]["attachment"] == 1
    assert got["census"]["mode"] == 1
    assert got["census"]["user"] == 1


def test_an_unparseable_line_is_counted_and_does_not_stop_the_read(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(json.dumps(_msg("user", "good", side=True)) + "\n{ not json\n",
                 encoding="utf-8")
    got = extract(p, sidechain_only=True, include_thinking=False)
    assert "good" in got["content"]
    assert got["census"]["UNPARSEABLE"] == 1


def test_a_session_filter_selects_one_conversation(tmp_path):
    p = _jsonl(tmp_path, [
        _msg("user", "from s1", side=True, session="s1"),
        _msg("user", "from s2", side=True, session="s2"),
    ])
    got = extract(p, sidechain_only=True, include_thinking=False, session="s2")
    assert "from s2" in got["content"] and "from s1" not in got["content"]


def test_empty_content_blocks_do_not_become_empty_turns(tmp_path):
    p = _jsonl(tmp_path, [
        _msg("assistant", [{"type": "thinking", "thinking": "only thinking"}], side=True),
        _msg("user", "real", side=True),
    ])
    got = extract(p, sidechain_only=True, include_thinking=False)
    assert len(got["turns"]) == 1


# --- the two refusals -------------------------------------------------------


def test_it_REFUSES_an_empty_extraction_rather_than_uploading_nothing(tmp_path, capsys):
    p = _jsonl(tmp_path, [_msg("user", "chair only", side=False)])
    rc = main(["--jsonl", str(p), "--run-id", "r", "--dry-run"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "REFUSED" in err
    assert "line types seen" in err
    assert "--all-turns" in err, "the refusal must name the knob to turn"


def test_it_REFUSES_over_budget_rather_than_truncating(tmp_path, capsys):
    p = _jsonl(tmp_path, [_msg("user", "x" * 5_000, side=True)])
    rc = main(["--jsonl", str(p), "--run-id", "r", "--dry-run", "--max-chars", "100"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "REFUSED" in err and "exceeds" in err
    assert "--max-chars" in err


def test_within_budget_it_prints_and_succeeds(tmp_path, capsys):
    p = _jsonl(tmp_path, [_msg("user", "small", side=True)])
    rc = main(["--jsonl", str(p), "--run-id", "r", "--dry-run"])
    assert rc == 0
    assert "small" in capsys.readouterr().out


def test_a_missing_file_is_a_usage_error_not_a_refusal(tmp_path):
    assert main(["--jsonl", str(tmp_path / "nope.jsonl"),
                 "--run-id", "r", "--dry-run"]) == 2
