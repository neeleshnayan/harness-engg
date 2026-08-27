"""THE LAMP SWITCH — fires automatically after every Agent dispatch.

The CEO's design (2026-08-27, verbatim): "let the agents flip a switch in
postgres when they run or trigger their sub-agents and UI just renders from
Postgres." This hook IS that switch: the harness invokes it after each Agent
tool call, it POSTs the dispatch to the spine, Postgres holds it, the floor
renders it. Zero chair discipline involved — which is the point, because
chair discipline is the component that failed four days running.

The OFF half: recording the run at resolve closes the lamp (the chair's
review act, per the constitution's closing-is-judgement rule). SHIPPED FOR
REAL 2026-08-27 in the spine's run recorder: a run record closes the seat's
single open dispatch automatically, or exactly the ids passed as
`closes_task_ids` when several are open — ambiguity closes NOTHING and the
response says which lamps remain, because guessing would close the wrong
crew's lamp. (An earlier version of this docstring claimed the auto-close
existed before it did; 15 lamps burned stale in one day and the CEO caught
it on the floor. A docstring is not a mechanism.)

Fail-open by design: a lamp that fails to light must never block a dispatch.
Any error prints to stderr (visible in hook logs) and exits 0.
"""
import json
import sys
import urllib.request

SEAT_MAP = {
    "builder": "builder", "quant": "quant", "adversary": "adversary",
    "analyst": "analyst", "mechanism": "mechanism", "pm": "pm",
    "validator": "validator", "riskofficer": "riskofficer", "coo": "coo",
    "cfo": "cfo", "secretary": "secretary",
}

def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001
        print(f"lamp_on: unreadable hook payload: {e}", file=sys.stderr)
        return 0
    if payload.get("tool_name") != "Agent":
        return 0
    tin = payload.get("tool_input") or {}
    seat = SEAT_MAP.get(str(tin.get("subagent_type", "")).strip().lower())
    if seat is None:
        # A general-purpose/foreign agent is not a seat; no lamp, no noise.
        return 0
    desc = str(tin.get("description") or "").strip()
    prompt_head = str(tin.get("prompt") or "")[:160].replace("\n", " ")
    task = desc or prompt_head or "(dispatch with no description)"
    body = json.dumps({"seat": seat, "task": f"{task} [auto-lamp]",
                       "actor": "cto"}).encode()
    req = urllib.request.Request(
        "http://localhost:8090/api/v1/fund/desk/dispatch", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            r.read()
    except Exception as e:  # noqa: BLE001
        print(f"lamp_on: spine unreachable, lamp not lit ({e})",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
