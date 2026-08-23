"""Mutation harness for D27 — byte level, CRLF aware, restores exact bytes.

Each mutant is (name, file, old, new). A mutant that no NAMED test kills is a
SURVIVOR and is reported as one. A mutant that provably changes nothing is
RETIRED, with the proof stated, never counted as killed.

    <venv>/Scripts/python.exe scratchpad/d27mutate.py
"""
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent / "d27"
PY = r"C:\Users\user\Documents\Krypton Fund\ClarkHarness\venv\Scripts\python.exe"

KG = "app/fund/knowledge.py"
EP = "app/fund/episodes.py"
RPT = "scripts/kg/report.py"
ING = "scripts/episodes/ingest.py"

T_EP = "tests/test_episodes.py"
T_KG = "tests/test_knowledge.py"
T_KGB = "tests/test_knowledge_backfill.py"
T_ISO = "tests/test_knowledge_isolation.py"

MUTANTS = [
    # --- ITEM 1(c) / the reader-writer split -------------------------------
    ("M01 reader ensures the schema again (the D27 regression)", KG,
     "    def _read(self, sql: str, params: tuple = ()) -> list[tuple]:",
     "    def _read(self, sql: str, params: tuple = ()) -> list[tuple]:\n"
     "        self.ensure_schema()", [T_KG]),
    ("M02 constructor ensures the schema again (the v1 defect)", KG,
     "        self._ensured = False\n\n    def _connect(self):\n"
     "        import psycopg\n        return psycopg.connect(self._dsn, autocommit=False)\n\n"
     "    def ensure_schema(self) -> bool:",
     "        self._ensured = False\n        self.ensure_schema()\n\n    def _connect(self):\n"
     "        import psycopg\n        return psycopg.connect(self._dsn, autocommit=False)\n\n"
     "    def ensure_schema(self) -> bool:", [T_KG]),
    ("M03 SchemaAbsent swallowed, reader returns []", KG,
     "        except psycopg.errors.UndefinedTable as e:\n"
     "            raise SchemaAbsent(",
     "        except psycopg.errors.UndefinedTable as e:\n"
     "            return []\n            raise SchemaAbsent(", [T_KG]),
    ("M04 ensure_schema not memoised (DDL on every write)", KG,
     "        if self._ensured:\n            return False\n"
     "        with self._connect() as conn:\n            with conn.cursor() as cur:\n"
     "                cur.execute(SCHEMA)\n            conn.commit()\n"
     "        self._ensured = True\n        return True\n\n    def _read",
     "        with self._connect() as conn:\n            with conn.cursor() as cur:\n"
     "                cur.execute(SCHEMA)\n            conn.commit()\n"
     "        self._ensured = True\n        return True\n\n    def _read", [T_KG]),
    ("M05 add_hypothesis stops ensuring the schema", KG,
     "        hid = (id or \"\").strip() or f\"kg-{uuid.uuid4().hex[:12]}\"\n"
     "        self.ensure_schema()",
     "        hid = (id or \"\").strip() or f\"kg-{uuid.uuid4().hex[:12]}\"", [T_KG]),

    # --- ITEM 1(a) the zero -------------------------------------------------
    ("M06 unclassified nulled again when the bucket is empty", KG,
     "    n = slot[\"n\"] if slot else 0",
     "    n = slot[\"n\"] if slot else 0\n"
     "    if not n:\n        return None", [T_KG]),
    ("M07 the two zero states share one note", KG,
     "    elif checked:\n        note = (f\"0 unclassified",
     "    elif True:\n        note = (f\"0 unclassified", [T_KG]),
    ("M08 report.py gates the block on truthiness again", RPT,
     "    u = d[\"unclassified\"]\n    L.append(\"\")",
     "    u = d[\"unclassified\"]\n    if not u[\"n\"]:\n        return \"\\n\".join(L)\n"
     "    L.append(\"\")", [T_KG]),
    ("M09 checked denominator dropped (0 of 0 reads clean)", KG,
     "    return {\"n\": n,\n            \"checked\": checked,",
     "    return {\"n\": n,\n            \"checked\": 0,", [T_KG]),

    # --- ITEM 1(b) recorded vs judged ---------------------------------------
    ("M10 recorded counts judged", KG,
     "            \"recorded\": len(hyps),\n            \"judged\": len(judged_ids),",
     "            \"recorded\": len(judged_ids),\n            \"judged\": len(judged_ids),",
     [T_KG, T_KGB]),
    ("M11 judged counts recorded", KG,
     "            \"recorded\": len(hyps),\n            \"judged\": len(judged_ids),",
     "            \"recorded\": len(hyps),\n            \"judged\": len(hyps),",
     [T_KG, T_KGB]),
    ("M12 the third status is dropped", KG,
     "            \"status\": \"TESTED\" if judged_ids else \"RECORDED_UNJUDGED\",",
     "            \"status\": \"TESTED\",", [T_KG, T_KGB]),
    ("M13 judged counts VOIDED outcomes too", KG,
     "        judged_ids = {o[\"hypothesis_id\"] for o in live}",
     "        judged_ids = {o[\"hypothesis_id\"] for o in outs}", [T_KG, T_KGB]),
    ("M14 the empty branch loses a key again", KG,
     "                \"killed\": 0,\n                \"provenance\": {p: 0 for p in PROVENANCES},",
     "                \"provenance\": {p: 0 for p in PROVENANCES},", [T_KG]),

    # --- ITEM 2: the void trigger ------------------------------------------
    ("M15 DELETE allowed", EP,
     "    IF TG_OP = 'DELETE' THEN\n        RAISE EXCEPTION 'fund_seat_episodes rows are never deleted",
     "    IF FALSE THEN\n        RAISE EXCEPTION 'fund_seat_episodes rows are never deleted",
     [T_EP]),
    ("M16 an ordinary UPDATE allowed", EP,
     "    IF NEW.voided IS NOT TRUE THEN",
     "    IF FALSE THEN", [T_EP]),
    ("M17 re-voiding allowed", EP,
     "    IF OLD.voided THEN\n        RAISE EXCEPTION 'episode % is already voided",
     "    IF FALSE THEN\n        RAISE EXCEPTION 'episode % is already voided", [T_EP]),
    ("M18 the narrow hole: the flip may edit the text", EP,
     "    IF NEW.seat        IS DISTINCT FROM OLD.seat\n"
     "    OR NEW.kind        IS DISTINCT FROM OLD.kind\n"
     "    OR NEW.heading     IS DISTINCT FROM OLD.heading\n"
     "    OR NEW.episode_md  IS DISTINCT FROM OLD.episode_md",
     "    IF NEW.seat        IS DISTINCT FROM OLD.seat\n"
     "    OR NEW.kind        IS DISTINCT FROM OLD.kind\n"
     "    OR NEW.heading     IS DISTINCT FROM OLD.heading", [T_EP]),
    ("M19 the narrow hole: the flip may re-tag", EP,
     "    OR NEW.market_tags IS DISTINCT FROM OLD.market_tags\n",
     "", [T_EP]),
    ("M20 a void needs no reason", EP,
     "    IF btrim(COALESCE(NEW.void_reason, '')) = '' THEN",
     "    IF FALSE THEN", [T_EP]),
    ("M21 a void needs no citing run", EP,
     "    IF btrim(COALESCE(NEW.voided_by_run, '')) = '' THEN",
     "    IF FALSE THEN", [T_EP]),
    ("M22 the trigger is never attached", EP,
     "CREATE TRIGGER fund_seat_episodes_immutable\n"
     "    BEFORE UPDATE OR DELETE ON fund_seat_episodes",
     "CREATE TRIGGER fund_seat_episodes_immutable\n"
     "    BEFORE INSERT ON fund_seat_episodes", [T_EP]),

    # --- ITEM 2: the episode reader/writer split ---------------------------
    ("M23 episode reader ensures the schema", EP,
     "    def _read(self, sql: str, params: tuple = ()) -> list[tuple]:",
     "    def _read(self, sql: str, params: tuple = ()) -> list[tuple]:\n"
     "        self.ensure_schema()", [T_EP]),
    ("M24 episode constructor ensures the schema", EP,
     "        self._ensured = False\n\n    def _connect(self):",
     "        self._ensured = False\n        self.ensure_schema()\n\n    def _connect(self):",
     [T_EP]),
    ("M25 episode ensure_schema not memoised", EP,
     "        if self._ensured:\n            return False\n"
     "        with self._connect() as conn:\n            with conn.cursor() as cur:\n"
     "                cur.execute(SCHEMA)\n            conn.commit()\n"
     "        self._ensured = True\n        return True",
     "        with self._connect() as conn:\n            with conn.cursor() as cur:\n"
     "                cur.execute(SCHEMA)\n            conn.commit()\n"
     "        self._ensured = True\n        return True", [T_EP]),

    # --- ITEM 2: the splitter ----------------------------------------------
    ("M26 the splitter strips each section", EP,
     "        out.append(Section(ordinal=i, heading=head, text=piece,",
     "        out.append(Section(ordinal=i, heading=head, text=piece.strip(),",
     [T_EP]),
    ("M27 the splitter drops the preamble", EP,
     "    pieces = [p for p in _SECTION_SPLIT_RE.split(markdown) if p != \"\"]",
     "    pieces = [p for p in _SECTION_SPLIT_RE.split(markdown)\n"
     "              if p != \"\" and p.startswith(\"## \")]", [T_EP]),
    ("M28 the splitter also splits on ###", EP,
     "_SECTION_SPLIT_RE = re.compile(r\"(?m)^(?=## )\")",
     "_SECTION_SPLIT_RE = re.compile(r\"(?m)^(?=##)\")", [T_EP]),
    ("M29 line_start is 0-based", EP,
     "                           line_start=line, line_end=line + n_lines - 1))",
     "                           line_start=line - 1, line_end=line + n_lines - 1))",
     [T_EP]),

    # --- ITEM 2: classification --------------------------------------------
    ("M30 kind rule order reversed (a carried STATE becomes a bind)", EP,
     "    (\"state\", r\"\\bSTATE\\b\"),\n    (\"evolve\", r\"\\bEVOLVE\\b\"),\n"
     "    (\"bind\", r\"\\bBINDS?\\b|\\bCARRIED\\b\"),",
     "    (\"bind\", r\"\\bBINDS?\\b|\\bCARRIED\\b\"),\n    (\"state\", r\"\\bSTATE\\b\"),\n"
     "    (\"evolve\", r\"\\bEVOLVE\\b\"),", [T_EP]),
    ("M31 tickers matched case-insensitively", EP,
     "    (tag, re.compile(pat, 0 if cs else re.IGNORECASE))",
     "    (tag, re.compile(pat, re.IGNORECASE))", [T_EP]),
    ("M32 the options tag is dropped from the vocabulary", EP,
     "    (\"options\", r\"\\bimplied vol|\\bstraddle\\b|\\boption chain\\b|\"\n"
     "                r\"\\bcall spread\\b|\\bput spread\\b\", False),\n",
     "", [T_EP, T_ISO]),
    ("M33 a bare 'options' is a market tag again", EP,
     "    (\"options\", r\"\\bimplied vol|\\bstraddle\\b|\\boption chain\\b|\"\n"
     "                r\"\\bcall spread\\b|\\bput spread\\b\", False),",
     "    (\"options\", r\"\\boptions?\\b\", False),", [T_EP]),
    ("M34 the tag vocabulary is a hand-kept literal", EP,
     "MARKET_TAGS: tuple[str, ...] = tuple(\n"
     "    dict.fromkeys(tag for tag, _, _ in MARKET_TAG_RULES))",
     "MARKET_TAGS: tuple[str, ...] = (\"equities\", \"bonds\", \"commodities\",\n"
     "                                \"fx\", \"crypto\", \"futures\", \"etf\")", [T_EP]),

    # --- ITEM 2: citations ---------------------------------------------------
    ("M35 a run-shaped token is accepted without the recorder", EP,
     "    if known is None:\n        return [], seen",
     "    if known is None:\n        return seen, []", [T_EP]),
    ("M36 the run id shape loses its second segment", EP,
     "RUN_ID_RE = re.compile(r\"\\brun-[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)+\")",
     "RUN_ID_RE = re.compile(r\"\\brun-[A-Za-z0-9]+\")", [T_EP]),
    ("M37 unknown tokens are silently dropped instead of reported", EP,
     "    return [t for t in seen if t in ks], [t for t in seen if t not in ks]",
     "    return [t for t in seen if t in ks], []", [T_EP]),

    # --- ITEM 2: the store's refusals ---------------------------------------
    ("M38 an unknown market tag is dropped instead of refused", EP,
     "        unknown = [t for t in tags if t not in MARKET_TAGS]",
     "        tags = [t for t in tags if t in MARKET_TAGS]\n"
     "        unknown = []", [T_EP]),
    ("M39 a blank citation is accepted", EP,
     "    text = value.strip() if isinstance(value, str) else \"\"\n    if not text:",
     "    text = value.strip() if isinstance(value, str) else \"\"\n    if False:", [T_EP]),

    # --- ITEM 2: absence in the reader --------------------------------------
    ("M40 voided rows are excluded but not counted", EP,
     "            \"voided_excluded\": 0 if include_voided else voided_total,",
     "            \"voided_excluded\": 0,", [T_EP]),
    ("M41 undated rows are excluded but not counted", EP,
     "            \"undated_excluded\": undated_total if dated else 0,",
     "            \"undated_excluded\": 0,", [T_EP]),
    ("M42 truncation is silent", EP,
     "        truncated = bool(limit) and len(rows) > int(limit or 0)",
     "        truncated = False", [T_EP]),
    ("M43 an empty store reads as a failed query", EP,
     "        if total == 0:\n            note = (\"THE STORE IS EMPTY",
     "        if False:\n            note = (\"THE STORE IS EMPTY", [T_EP]),
    ("M44 a seat with no rows at all is not named as such", EP,
     "            if seat and seat.strip().lower() not in seats_in_store:",
     "            if False:", [T_EP]),
    ("M45 an unknown kind filter matches nothing instead of refusing", EP,
     "            if kind not in KINDS:\n                raise ValueError(f\"kind must be one of {KINDS}, got {kind!r}\")",
     "            pass", [T_EP]),

    # --- ITEM 2: the ingest --------------------------------------------------
    ("M46 the ingest identity uses the verbatim bytes again", ING,
     "        digest = hashlib.sha256(\n"
     "            s.text.rstrip().encode(\"utf-8\")).hexdigest()[:16]",
     "        digest = hashlib.sha256(s.text.encode(\"utf-8\")).hexdigest()[:16]",
     [T_EP]),
    ("M47 the ingest drops the ordinal from the key", ING,
     "            \"dedupe_key\": f\"episodes:{seat}:{s.ordinal:04d}:{digest}\",",
     "            \"dedupe_key\": f\"episodes:{seat}:{digest}\",", [T_EP]),
    ("M48 empty-bodied sections are dropped rather than stored", ING,
     "            if r[\"empty_body\"]:\n                totals[\"empty_body\"] += 1",
     "            if r[\"empty_body\"]:\n                totals[\"empty_body\"] += 1\n"
     "                continue", [T_EP]),
    ("M49 uninterpretable sections are counted but not named", ING,
     "                uninterpretable.append({",
     "                _ = ({", [T_EP]),
    ("M50 an absent state dir reports a clean zero", ING,
     "    if not state_dir.is_dir():\n        raise SystemExit(",
     "    if False:\n        raise SystemExit(", [T_EP]),
    ("M51 a dir with no seat files reports a clean zero", ING,
     "    if not files:\n        raise SystemExit(",
     "    if False:\n        raise SystemExit(", [T_EP]),
    ("M52 instrument files are ingested as seats", ING,
     "SEAT_STEM_RE = re.compile(r\"^[a-z][a-z-]*$\")",
     "SEAT_STEM_RE = re.compile(r\"^[A-Za-z][A-Za-z_-]*$\")", [T_EP]),
    ("M53 the dry run writes after all", ING,
     "    store = None\n    if not dry_run:",
     "    store = None\n    if True:", [T_EP]),
    ("M54 the ingest reports only tags that fired", ING,
     "        \"market_tags\": {t: tags.get(t, 0) for t in MARKET_TAGS},",
     "        \"market_tags\": dict(sorted(tags.items())),", [T_EP]),

    # --- the isolation guards ------------------------------------------------
    ("M55 the episode store drops its WORK_LAYER_STORE declaration", EP,
     "WORK_LAYER_STORE = True", "WORK_LAYER_STORE = False", [T_ISO]),
    ("M56 the layer scan accepts any assignment, not True", T_ISO,
     "                and isinstance(node.value, ast.Constant)\n"
     "                and node.value.value is True):",
     "                and isinstance(node.value, ast.Constant)):", [T_ISO]),
    ("M57 the protected-column census loses a column", EP,
     "    OR NEW.source_ref  IS DISTINCT FROM OLD.source_ref\n", "", [T_EP]),
    ("M58 the void flip may rewrite the seat", EP,
     "    IF NEW.seat        IS DISTINCT FROM OLD.seat\n    OR NEW.kind",
     "    IF NEW.kind", [T_EP]),
]


def run(tests):
    r = subprocess.run(
        [PY, "-m", "pytest", *tests, "-q", "-x", "-p", "no:randomly",
         "--no-header", "-W", "ignore"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    killed, survived, not_applied = [], [], []
    for name, rel, old, new, tests in MUTANTS:
        if only and not name.startswith(only):
            continue
        p = ROOT / rel
        original = p.read_bytes()
        text = original.decode("utf-8")
        # CRLF ON DISK: patterns are written with \n, so translate before
        # matching. D19: six real mutants were reported NOT-APPLIED because of
        # exactly this, and NOT-APPLIED is not a retirement.
        nl = "\r\n" if "\r\n" in text else "\n"
        o = old.replace("\n", nl)
        n = new.replace("\n", nl)
        if text.count(o) != 1:
            not_applied.append(f"{name}  (pattern found {text.count(o)}x)")
            continue
        p.write_bytes(text.replace(o, n).encode("utf-8"))
        try:
            rc, out = run(tests)
        finally:
            p.write_bytes(original)
        if rc == 0:
            survived.append(name)
            print(f"SURVIVED  {name}")
        else:
            first = next((ln for ln in out.splitlines()
                          if ln.startswith("FAILED") or "Error" in ln), "")
            killed.append((name, first.strip()[:120]))
            print(f"killed    {name}\n              by {first.strip()[:110]}")
    print(f"\n{len(killed)} killed, {len(survived)} SURVIVED, "
          f"{len(not_applied)} NOT APPLIED")
    for s in survived:
        print(f"  SURVIVOR      {s}")
    for s in not_applied:
        print(f"  NOT APPLIED   {s}")
    # A restored file must be byte-identical. D18: a harness that rewrote with
    # newline="\n" left zero-line-diff modified files in git status.
    st = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                        capture_output=True, text=True)
    print(f"\ngit status after restore:\n{st.stdout or '  (clean)'}")


if __name__ == "__main__":
    main()
