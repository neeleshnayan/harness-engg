"""Byte-level mutation harness for D24 (the D22 repair round).

Same shape as mutate_d22.py: CRLF-aware, restores exact bytes, one mutant at a
time, KILLED if any named test fails. Every mutant here breaks a branch this
dispatch ADDED — a repair whose defect can come back unnoticed is not a repair.
"""
import subprocess, sys, os, json

ROOT = r"C:/Users/user/AppData/Local/Temp/claude/C--Users-user-Documents-Krypton-Fund/bbc88cbf-5b81-4236-8781-b009121ec21f/scratchpad/d22ch"
PY = r"C:/Users/user/Documents/Krypton Fund/ClarkHarness/venv/Scripts/python.exe"
TESTS = ["tests/test_desk_engine.py", "tests/test_desk_engine_store.py",
         "tests/test_desk.py", "tests/test_desk_load_actor.py"]

E = "app/fund/deskengine.py"
F = "app/api/v1/fund.py"
D = "app/fund/desk.py"

MUTANTS = [
 # ---------------------------------------- repair 3: canonicalise on write --
 ("N1", E, "        rid = str(uuid.UUID(rid))",
        "        rid = rid",
        "req_ref stops normalising a UUID's case"),
 ("N2", E, '    if parsed["kind"] == "req":\n        return req_ref(parsed["request_id"])\n    return rec_ref(parsed["run_id"], parsed["rec_id"])',
        '    return ref',
        "canonical_ref returns the raw ref it was handed"),
 ("N3", E, "        target_ref = canonical_ref(target_ref)",
        "        target_ref = target_ref",
        "add() stores the raw target (validate-stripped / store-raw returns)"),
 ("N4", E, "            superseder_ref = canonical_ref(superseder_ref)",
        "            superseder_ref = superseder_ref",
        "add() stores the raw superseder"),
 ("N5", E, "        self.migration_report = self.canonicalise_stored()",
        "        self.migration_report = {'rewritten': 0}",
        "the pre-repair migration never runs"),
 ("N6", E, '                report["unparseable"].append(row["edge_id"])',
        '                pass',
        "an unparseable stored ref is silently skipped"),
 ("N7", E, '                report["conflicts"].append({"edge_id": row["edge_id"],',
        '                [].append({"edge_id": row["edge_id"],',
        "a migration collision is swallowed"),
 # ------------------------------------------- repair 2: truncation is loud --
 ("N8", E, '"ORDER BY applied_at DESC LIMIT %s", (*params, limit + 1))',
        '"ORDER BY applied_at DESC LIMIT %s", (*params, limit))',
        "fetch exactly the limit: truncation becomes invisible again"),
 ("N9", E, "        truncated = len(rows) > limit",
        "        truncated = len(rows) >= limit",
        "a full page is misreported as truncated"),
 ("N10", E, "        rows, truncated = self._page(where, params, limit)\n        if truncated:",
         "        rows, truncated = self._page(where, params, limit)\n        if False:",
         "_select stops raising: the silent cap is back"),
 ("N11", E, "        if limit is None:\n            limit = EDGE_QUERY_LIMIT",
         "        if limit is None:\n            limit = 1000",
         "the query stops READING the limit constant"),
 # ------------------------------- repairs 1/4/5: disclosure, record, parity --
 ("N12", F, "    try:\n        s = _supersessions()\n        if s is None:\n            return None\n        return s.by_target()",
         "    s = _supersessions()\n    try:\n        if s is None:\n            return None\n        return s.by_target()",
         "store construction back OUTSIDE the try (cache-warmth policy)"),
 ("N13", F, '        return {"refusal": approval_refusal(ref, edges),\n                "supersession_readable": edges is not None}',
         '        return {"refusal": approval_refusal(ref, edges),\n                "supersession_readable": True}',
         "the disclosure always claims the check ran"),
 ("N14", F, '               "supersession_readable": readable,\n               "at": datetime.now(timezone.utc).isoformat()}\n    _store.append(Event(aggregate_id=request_id, aggregate_type="desk_request",',
         '               "at": datetime.now(timezone.utc).isoformat()}\n    _store.append(Event(aggregate_id=request_id, aggregate_type="desk_request",',
         "the approve payload drops the disclosure"),
 ("N15", F, "    _store.append(Event(\n        aggregate_id=target_id, aggregate_type=kind,\n        type=EventType.APPROVAL_REFUSED,",
         "    _noop = (Event, EventType)\n    if False:\n        _store.append(Event(\n        aggregate_id=target_id, aggregate_type=kind,\n        type=EventType.APPROVAL_REFUSED,",
         "the supersession refusal stops recording its event"),
 ("N16", F, '    actor = _guard_approval("desk_request", request_id, req.actor, req.confirm,\n                            req.instruction, DESK_APPROVAL_ALLOWLIST)\n    readable = _refuse_if_superseded(req_ref(request_id), kind="desk_request",\n                                     target_id=request_id, actor=actor)',
         '    readable = _refuse_if_superseded(req_ref(request_id), kind="desk_request",\n                                     target_id=request_id, actor=req.actor)\n    actor = _guard_approval("desk_request", request_id, req.actor, req.confirm,\n                            req.instruction, DESK_APPROVAL_ALLOWLIST)',
         "the order flips back: lineage handed out before identity"),
 ("N17", F, '    except Exception as e:  # noqa: BLE001\n        # THE POLICY IS THE POLICY WHEREVER THE FAILURE HAPPENS.',
         '    except ZeroDivisionError as e:  # noqa: BLE001\n        # THE POLICY IS THE POLICY WHEREVER THE FAILURE HAPPENS.',
         "a failure above the store 500s the approval path again"),
 ("N18", F, "    readable = None\n    if req.status in ADVANCING_REC_STATUSES:",
         "    readable = True\n    if req.status in ADVANCING_REC_STATUSES:",
         "a non-advancing decision claims a check nobody ran"),
 ("N19", F, "    edges, truncated = s.page(include_retracted=include_retracted)",
         "    edges, truncated = s.page(include_retracted=include_retracted)[0], False",
         "the edge list stops declaring its truncation"),
 # -------------------------------------------- repair 6: the routing flag ---
 ("N20", D, "DESK_ROUTING_ENFORCE = False",
         "DESK_ROUTING_ENFORCE = True",
         "the flag ships ON (the half-shipped contract returns)"),
 ("N21", D, "    if enforce is None:\n        enforce = DESK_ROUTING_ENFORCE\n    if not enforce:\n        return []",
         "    if enforce is None:\n        enforce = DESK_ROUTING_ENFORCE",
         "validate_routing ignores the gate entirely"),
 ("N22", D, "ROUTING_ENFORCED_FROM_VERSION = 1",
         "ROUTING_ENFORCED_FROM_VERSION = 2",
         "the opt-in threshold moves out from under a declared v1"),
 ("N23", F, "    enforce = bool(desk_mod.DESK_ROUTING_ENFORCE) or (\n        declared is not None\n        and declared >= desk_mod.ROUTING_ENFORCED_FROM_VERSION)",
         "    enforce = bool(desk_mod.DESK_ROUTING_ENFORCE)",
         "a run may no longer opt in ahead of the fleet"),
 ("N24", F, "    if findings and enforce:",
         "    if findings:",
         "the door enforces regardless of the flag"),
 ("N25", F, '    if findings:\n        # STORED, AND TOLD.',
         '    if False:\n        # STORED, AND TOLD.',
         "the advisory disappears: nobody knows what the flip would cost"),
 # ---------------------------------------- the late read-through's own two --
 ("N26", F, '            "total": s.count(include_retracted=include_retracted),',
         '            "total": len(edges),',
         "the capped list reports its page as the table's size"),
 ("N27", E, '        rows, truncated = self._page("", (), MIGRATION_SCAN_LIMIT)',
         '        rows, truncated = self._page("", (), MIGRATION_SCAN_LIMIT)[0], False',
         "a partial migration reports itself complete"),
]


def read(p):
    with open(os.path.join(ROOT, p), "rb") as f:
        return f.read()


def write(p, b):
    with open(os.path.join(ROOT, p), "wb") as f:
        f.write(b)


def encodings(s):
    return [s.replace("\n", "\r\n").encode("utf-8"), s.encode("utf-8")]


def run_tests():
    r = subprocess.run([PY, "-m", "pytest", "-x", "-q", *TESTS],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, (r.stdout or "")[-2500:]


def name_of(out):
    for line in out.splitlines():
        if line.startswith("FAILED ") or ("::" in line and line.startswith("tests")):
            return line.strip()[:160]
    return "(no named test in tail)"


def main():
    only = sys.argv[1:] or None
    results = []
    for mid, path, find, repl, note in MUTANTS:
        if only and mid not in only:
            continue
        original = read(path)
        hits = [(f, r) for f, r in zip(encodings(find), encodings(repl))
                if original.count(f) == 1]
        if not hits:
            counts = [original.count(f) for f in encodings(find)]
            results.append((mid, "NOT-APPLIED", note,
                            f"pattern matches {counts} times (crlf, lf)"))
            print(f"{mid} NOT-APPLIED  {note} counts={counts}")
            continue
        f, r = hits[0]
        try:
            write(path, original.replace(f, r, 1))
            code, out = run_tests()
            verdict = "killed" if code != 0 else "SURVIVED"
            who = name_of(out) if code != 0 else ""
            results.append((mid, verdict, note, who))
            print(f"{mid} {verdict:9s} {note}\n       {who}")
        finally:
            write(path, original)
    print("\n=== summary ===")
    for mid, v, note, who in results:
        print(f"{mid:5s} {v:12s} {note}")
    print(json.dumps({v: sum(1 for x in results if x[1] == v)
                      for v in {x[1] for x in results}}))


if __name__ == "__main__":
    main()
