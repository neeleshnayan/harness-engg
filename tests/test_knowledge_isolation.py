"""THE GRAPH NEVER GATES — asserted over the tree, not promised in a docstring.

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

#: The module the control layer may not reach.
FORBIDDEN = "app.fund.knowledge"

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


def _app_modules() -> list[pathlib.Path]:
    return sorted(p for p in APP.rglob("*.py") if p.name != "__init__.py")


def test_no_module_under_app_imports_the_knowledge_graph():
    """Nothing in the spine reads it — not even the endpoint layer, today.

    Widened deliberately from DECISION_PATH to the whole of ``app/``: v1 ships
    with NO consumer inside the process, and the strongest statement available
    is that the graph is reachable only from ``scripts/`` and ``tests/``. If a
    read-only endpoint is added later this assertion narrows to DECISION_PATH
    by a one-line change and a written reason — which is the point: the
    loosening has to be typed out.
    """
    offenders = [str(p.relative_to(ROOT)) for p in _app_modules()
                 if any(n == FORBIDDEN or n.startswith(FORBIDDEN + ".")
                        for n in _imports(p))]
    assert offenders == [], (
        "the knowledge graph is WORK LAYER and must not become load-bearing "
        "under anything in the spine: " + ", ".join(offenders))


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


@pytest.mark.parametrize("name", ["family_ledger", "prediction_calibration",
                                  "kill_taxonomy", "cheap_kills"])
def test_every_reader_has_a_caller(name):
    """NO READER SHIPS UNWIRED.

    Four query functions with no caller are the unwired-kill-switch pattern in
    a reporting costume: they look done and answer nobody. ``scripts/kg/
    report.py`` is the consumer, and this asserts the wiring rather than
    trusting it.
    """
    text = (ROOT / "scripts" / "kg" / "report.py").read_text(encoding="utf-8")
    assert f".{name}(" in text, (
        f"{name} has no caller in scripts/kg/report.py — a reader nobody runs "
        f"is not a feature")
