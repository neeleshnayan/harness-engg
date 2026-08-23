"""THE WORK-LAYER STORES NEVER GATE — asserted over the tree, not promised in
a docstring.

Design rule 4: "No threshold reads it; the gate never consults it. It shapes
what Ed PROPOSES and what the chair puts in BRIEFS. (Work layer — one commit to
revert; the control layer cannot grow a dependency on it without a versioned
human decision.)"

A rule like that decays the ordinary way: someone needs a family count inside a
criterion, adds one import, and the work layer is now load-bearing under the
control layer. The check is cheap and it fails on the author who does it.

No Postgres required — this reads source, so it runs on every machine.
"""

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app"

#: The modules the control layer may not reach, DERIVED from the modules
#: themselves rather than listed here.
#:
#: A work-layer store declares ``WORK_LAYER_STORE = True`` at module level and
#: this scan finds it. The law is one law — a work-layer store the spine
#: imports has become load-bearing under the control layer, whichever store it
#: is — and a hand-kept tuple is the wrong shape for it: mutation showed that
#: deleting an entry ran one fewer parametrized case and failed nothing at all.
#: Now the only way to leave a store unpoliced is to delete its own
#: declaration, which fails on the author who does it
#: (``test_the_derived_forbidden_set_is_exactly_the_stores_we_know_about``).
def _declares_work_layer(path: pathlib.Path) -> bool:
    """Does this module declare ``WORK_LAYER_STORE = True`` at module level?

    Takes a PATH so the scanner can be run over planted code — an AST guard
    whose scope is a hardcoded directory cannot be tested against the shapes
    it is supposed to reject, and the adversary's D18 carry says to run one
    over planted code in every construction shape the codebase uses.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "WORK_LAYER_STORE"
                        for t in node.targets)
                and isinstance(node.value, ast.Constant)
                and node.value.value is True):
            return True
    return False


def _work_layer_modules(directory: pathlib.Path | None = None) -> tuple[str, ...]:
    d = directory or (APP / "fund")
    return tuple(f"app.fund.{p.stem}" for p in sorted(d.glob("*.py"))
                 if _declares_work_layer(p))


FORBIDDEN_MODULES = _work_layer_modules()


@pytest.mark.parametrize("source,declares", [
    ("WORK_LAYER_STORE = True\n", True),
    ("WORK_LAYER_STORE = False\n", False),
    ("WORK_LAYER_STORE = 1\n", False),
    ("WORK_LAYER_STORE = None\n", False),
    ('"""A docstring saying WORK_LAYER_STORE = True."""\nX = 1\n', False),
    ("def f():\n    WORK_LAYER_STORE = True\n", False),
    ("class C:\n    WORK_LAYER_STORE = True\n", False),
    ("X = 1\n", False),
])
def test_the_layer_scan_reads_the_declaration_and_nothing_that_looks_like_one(
        source, declares, tmp_path):
    """``= False`` and ``= 1`` must NOT count.

    Mutation found this: dropping the ``is True`` check survived every other
    test, because both real modules declare True and the mutant was a no-op on
    today's tree. A module-level constant inside a function or a class body is
    not a module-level declaration either, and neither is a docstring that
    mentions one.
    """
    p = tmp_path / "planted.py"
    p.write_text(source, encoding="utf-8")
    assert _declares_work_layer(p) is declares

#: Kept as a name because the planted-import test reads like prose with it.
FORBIDDEN = "app.fund.knowledge"


def test_the_derived_forbidden_set_is_exactly_the_stores_we_know_about():
    """The specification side of the derivation, hardcoded on purpose.

    The scan above says what the tree declares; this says what the firm has
    decided. Both are needed: a scan alone goes green by finding nothing, and
    a literal alone goes stale. When a third work-layer store ships, this line
    is the one that makes somebody type its name.
    """
    assert set(FORBIDDEN_MODULES) == {"app.fund.knowledge", "app.fund.episodes"}, (
        f"the WORK_LAYER_STORE declarations in app/fund do not match the "
        f"stores this guard was written for: {FORBIDDEN_MODULES}")


def _reaches(names, forbidden) -> bool:
    return any(n == forbidden or n.startswith(forbidden + ".") for n in names)

#: Where a dependency would actually cost money. Named explicitly rather than
#: "everything under app/" for one reason: the honest future includes a
#: read-only ENDPOINT, and an endpoint is not a decision path. The list is the
#: control layer as the constitution names it — the gate, the auto-approval
#: policy, the risk engine, the order pipeline, the exit mechanics, the belt,
#: and the event store.
DECISION_PATH = (
    "gate.py", "autopolicy.py", "factory.py", "risk.py", "riskmonitor.py",
    "pipeline.py", "exitrule.py", "leanrunner.py", "judgement.py",
    "events.py", "pgstore.py", "chain.py", "walkforward.py", "compliance.py",
)


def _imports(path: pathlib.Path) -> set[str]:
    """Every module name this file imports, at any depth of the AST.

    Walks the tree rather than scanning the first N lines: a deferred import
    inside a function is exactly how this dependency would arrive, and reading
    only the header would miss the one shape that matters. This codebase uses
    function-local imports throughout, deliberately.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def _code_strings(path: pathlib.Path) -> set[str]:
    """Every string literal in this file EXCEPT docstrings.

    Comments never reach the AST at all, which is the other half of why this
    reads the tree instead of the text: a scan over raw source cannot tell a
    path somebody builds from a path somebody mentions.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings}


def _app_modules() -> list[pathlib.Path]:
    return sorted(p for p in APP.rglob("*.py") if p.name != "__init__.py")


@pytest.mark.parametrize("forbidden", FORBIDDEN_MODULES)
def test_no_module_under_app_imports_a_work_layer_store(forbidden):
    """Nothing in the spine reads them — not even the endpoint layer, today.

    Widened deliberately from DECISION_PATH to the whole of ``app/``: both
    stores ship with NO consumer inside the process, and the strongest
    statement available is that they are reachable only from ``scripts/`` and
    ``tests/``. If a read-only endpoint is added later this assertion narrows
    to DECISION_PATH by a one-line change and a written reason — which is the
    point: the loosening has to be typed out.
    """
    offenders = [str(p.relative_to(ROOT)) for p in _app_modules()
                 if p.stem != forbidden.rsplit(".", 1)[1]
                 and _reaches(_imports(p), forbidden)]
    assert offenders == [], (
        f"{forbidden} is WORK LAYER and must not become load-bearing under "
        f"anything in the spine: " + ", ".join(offenders))


@pytest.mark.parametrize("forbidden", FORBIDDEN_MODULES)
def test_the_forbidden_modules_this_guard_names_EXIST(forbidden):
    """Absence discipline on the guard. A renamed module would make the scan
    above pass by looking for something that is not there."""
    assert (APP / "fund" / f"{forbidden.rsplit('.', 1)[1]}.py").exists()


def test_the_two_work_layer_stores_do_not_import_EACH_OTHER():
    """They share three rules and must not share an import.

    ``episodes.py`` restates ``SchemaAbsent`` and ``_cite`` rather than
    importing them, deliberately: an import in either direction would make one
    guard's scan pass through the other module, and the whole point of the
    scan is that each store is reachable only from scripts and tests.
    """
    for a, b in (("knowledge", "episodes"), ("episodes", "knowledge")):
        names = _imports(APP / "fund" / f"{a}.py")
        assert not _reaches(names, f"app.fund.{b}"), (
            f"{a}.py imports {b}.py — the isolation guards are per module and "
            f"an import between them routes around one of them")


def test_the_decision_path_modules_this_guard_names_all_exist():
    """Absence discipline on the guard itself.

    A misspelt filename here would make the check above pass by looking at
    nothing — the same defect as an empty scan reported as a clean one.
    """
    missing = [n for n in DECISION_PATH if not (APP / "fund" / n).exists()]
    assert missing == [], (
        f"DECISION_PATH names files that do not exist: {missing}. Either they "
        f"were renamed and this list is now watching nothing, or the list has "
        f"a typo.")


def test_the_scan_finds_a_planted_import():
    """A guard that cannot fail is not a guard.

    Feeds the walker the exact shape the dependency would arrive in — a
    function-local import inside a criterion — and requires a hit.
    """
    import tempfile
    forged = ("def criterion(x):\n"
              "    from app.fund.knowledge import KnowledgeGraph\n"
              "    return KnowledgeGraph().family_ledger('f')\n")
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "planted.py"
        p.write_text(forged, encoding="utf-8")
        names = _imports(p)
    assert any(n == FORBIDDEN or n.startswith(FORBIDDEN + ".") for n in names)


def test_the_scan_actually_reads_the_tree():
    """The other half: prove the walker sees real files and real imports."""
    mods = _app_modules()
    assert len(mods) > 50, (
        f"only {len(mods)} modules found under app/ — the glob is looking in "
        f"the wrong place rather than finding a small tree")
    gate = APP / "fund" / "gate.py"
    assert "app.fund" in {n.rsplit(".", 1)[0] for n in _imports(gate)} or \
        any(n.startswith("app.") for n in _imports(gate)), (
        "gate.py imports nothing from app.* — the walker is not reading it")


def test_the_knowledge_module_does_not_import_the_control_layer_either():
    """The dependency is forbidden in BOTH directions.

    Importing ``gate.py`` to reuse its failure sentences would couple the
    graph's history to a module that is versioned by human decision, and a
    reworded gate would silently re-slug five years of stored kills. The slug
    table is local and says so.
    """
    names = _imports(APP / "fund" / "knowledge.py")
    forbidden = [n for n in names
                 if n.startswith("app.fund.")
                 and n.split(".")[2] in {"gate", "autopolicy", "factory",
                                         "risk", "riskmonitor", "pipeline",
                                         "exitrule", "leanrunner"}]
    assert forbidden == [], (
        "knowledge.py must not import a control-layer module: "
        + ", ".join(forbidden))


@pytest.mark.parametrize("script,name", [
    ("kg/report.py", "family_ledger"),
    ("kg/report.py", "prediction_calibration"),
    ("kg/report.py", "kill_taxonomy"),
    ("kg/report.py", "cheap_kills"),
    ("episodes/query.py", "episodes"),
    ("episodes/query.py", "coverage"),
    ("episodes/query.py", "seats"),
    ("episodes/query.py", "tags"),
])
def test_every_reader_has_a_caller(script, name):
    """NO READER SHIPS UNWIRED.

    Query functions with no caller are the unwired-kill-switch pattern in a
    reporting costume: they look done and answer nobody. The scripts are the
    consumers, and this asserts the wiring rather than trusting it.

    ``seats`` and ``tags`` are called INDIRECTLY, from inside ``episodes()`` —
    which is why the check is "the name appears in the script" for the two the
    script calls itself and why they are also exercised through the reader in
    ``tests/test_episodes.py``. A grep-shaped guard cannot see an indirect
    call; the behavioural test can.
    """
    text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    store_text = (ROOT / "app" / "fund" / (
        "knowledge.py" if script.startswith("kg/") else "episodes.py")
    ).read_text(encoding="utf-8")
    assert f".{name}(" in text or f"self.{name}(" in store_text, (
        f"{name} has no caller in scripts/{script} — a reader nobody runs is "
        f"not a feature")


def test_no_module_under_app_reads_the_seat_memoranda():
    """``.claude/state`` is the operating memory and the spine never touches it.

    The episode store is a COPY; the day something in ``app/`` reads the
    markdown directly, the copy has a competitor and the two will disagree.
    Checked over STRING LITERALS rather than raw source, and docstrings are
    excluded — the first draft of this test flagged ``desk.py`` and
    ``episodes.py``, both of which merely NAME ``.claude`` in prose. A guard
    that fires on a docstring gets deleted by the third person it annoys, and
    then it is not guarding anything.
    """
    offenders = sorted({str(p.relative_to(ROOT)) for p in _app_modules()
                        if any(".claude" in s for s in _code_strings(p))})
    assert offenders == [], (
        "a module under app/ builds a path into .claude — the seat memoranda "
        "are read by scripts/episodes/ingest.py and nothing else: "
        + ", ".join(offenders))


def test_the_seat_memoranda_scan_finds_a_planted_path():
    """A guard that cannot fail is not a guard — and this one has two ways to
    be vacuous, so both are checked: it must SEE a real path literal and it
    must IGNORE the same text in a docstring."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        real = pathlib.Path(d) / "planted.py"
        real.write_text('import pathlib\n'
                        'P = pathlib.Path(".claude") / "state"\n',
                        encoding="utf-8")
        prose = pathlib.Path(d) / "prose.py"
        prose.write_text('"""We never read .claude/state here."""\n'
                         'X = 1\n', encoding="utf-8")
        assert any(".claude" in s for s in _code_strings(real))
        assert not any(".claude" in s for s in _code_strings(prose))
