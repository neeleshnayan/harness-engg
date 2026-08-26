"""Live LEAN sessions: the decisions, with no IO in them.

**WHY THIS MODULE EXISTS SEPARATELY FROM THE RUNNER.** Three facts about a live
session are decided by rules and not by a database or a docker daemon: which
sessions may coexist (the scope key), what a running container with no registry
row IS (the reconciliation), and what the fence's anchor may honestly claim
(the known-since decision). Each one is a multi-field state, and this fund has
already paid twice for multi-field states assembled by their callers — the
endpoint that handed ``engine_status`` an empty session list and then patched
two of five fields, shipping a payload that contradicted itself on the one path
no test covered. So each is computed HERE, once, from ONE input, and the runner
does the IO and hands the answers over.

**EVERY INPUT IS THREE-VALUED AND ITS UNREADABLE CASE IS ITS OWN VALUE.**
``containers=None`` is "docker could not be asked"; ``containers=[]`` is "docker
was asked and nothing is running". Those lead to OPPOSITE actions — the first
must stop nothing and conclude nothing, the second may mark every live row
vanished — and collapsing them is how "we could not look" becomes "everything
is gone".
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

#: Container names for live sessions. ``leanrunner.start_live`` builds the name
#: as this prefix plus the session id, and the reconciler recovers the id by
#: stripping it. One constant so the two halves cannot drift.
CONTAINER_PREFIX = "lean-live-"

#: Docker label carrying the fund MODE that started a container. Added 2026-08-27
#: with the session registry: two spines in different modes share one docker
#: daemon and one ``lean-live-`` namespace, so without this the second spine
#: would classify the first's container as an unknown orphan and stop it. A
#: LABEL rather than a name change because the container name is already read by
#: ``stop_live`` and by a session running right now.
MODE_LABEL = "krypton.fund.mode"

#: The states in which a session is claiming a container. Kept identical to
#: ``engineledger._SESSION_ALIVE`` and pinned by a test: two ideas of "alive" is
#: the second-opinion defect the fence was built to avoid.
ALIVE = ("starting", "running")

#: A row said running and no container backs it. NOT ``ended`` (which means the
#: engine exited and we read its return code) and NOT ``stopped`` (which means a
#: human asked for it). Three different facts get three different words, because
#: the only one that says "we do not know how it died" is this one.
VANISHED = "vanished"

# --- what the reconciler decides to do about one container -------------------

#: The registry knows this session and believes it alive: take it back into the
#: process's session table so it is stoppable again.
REATTACH = "reattach"

#: The registry has a row and believes it DEAD, and the container is running.
#: The container is the fact; adopt it and record the contradiction loudly.
ADOPT = "adopt"

#: No registry row at all. A container the fund cannot account for, holding a
#: signal token and able to POST proposals into the approval queue.
STOP = "stop"

#: Labelled for another fund mode, or ownership unjudgeable. Recorded, never
#: touched — stopping is destructive and an unproven claim of ownership is not
#: a licence to act on it.
LEAVE = "leave"

OWN_OURS = "ours"
OWN_LEGACY = "legacy"          # unlabelled: started before MODE_LABEL existed
OWN_FOREIGN = "foreign"        # labelled for a different mode
OWN_UNJUDGEABLE = "unjudgeable"  # labelled, but our own mode could not be read


def scope_key(strategy_id: Any, algorithm: Any) -> str:
    """The identity a live session is UNIQUE on, as one string.

    One live session per strategy is the rule the CEO's autopilot decision
    needs. But ``start_live`` accepts an empty ``strategy_id`` — the Lab starts
    unscoped sessions — and two unscoped sessions of the same algorithm are the
    same hazard wearing no name: ``engineledger._claiming_session`` matches a
    signal on strategy id OR algorithm, so two of either make one signal
    claimable by two books.

    So the key is the strategy when there is one and the algorithm when there is
    not. Computed in ONE place because the database's unique index and the
    in-process guard must agree on it exactly; two spellings of this rule is two
    different uniqueness rules.
    """
    sid = str(strategy_id or "").strip()
    if sid:
        return f"strategy:{sid}"
    algo = str(algorithm or "").strip()
    if algo:
        return f"algorithm:{algo}"
    # Not reachable through start_live (an algorithm is required and resolved
    # before this is called) and still not silently collapsed to "": an empty
    # key would make every unidentifiable session collide with every other one,
    # which is a refusal dressed as a rule.
    return "unidentified:"


def is_alive(row: Any) -> bool:
    """Alive == claiming a container. Absence is not alive."""
    if not isinstance(row, dict):
        return False
    return str(row.get("state") or "") in ALIVE


def session_id_of(container_name: Any) -> Optional[str]:
    """The session id inside a container name, or ``None``.

    Strict prefix, not ``in``: ``docker ps --filter name=`` is a SUBSTRING
    match, so a container called ``mine-lean-live-x`` comes back from the same
    query and is not ours.
    """
    name = str(container_name or "")
    if not name.startswith(CONTAINER_PREFIX):
        return None
    sid = name[len(CONTAINER_PREFIX):].strip()
    return sid or None


def ownership(container_mode: Any, our_mode: Any) -> str:
    """Whose container is this — read from the label, never guessed.

    An UNLABELLED container is ours by name (it predates the label). A container
    labelled for another mode is never ours. And if we cannot read our OWN mode
    we cannot judge a labelled container at all, which is its own value rather
    than a guess in either direction — the action attached to it is "leave it
    alone", because the destructive branch must never run on an unproven claim.
    """
    cm = str(container_mode or "").strip()
    om = str(our_mode or "").strip()
    if not cm:
        return OWN_LEGACY
    if not om:
        return OWN_UNJUDGEABLE
    return OWN_OURS if cm == om else OWN_FOREIGN


def _touchable(own: str) -> bool:
    """Ours to reattach, adopt or stop."""
    return own in (OWN_OURS, OWN_LEGACY)


def reconcile(rows: Optional[list[dict[str, Any]]],
              containers: Optional[Iterable[dict[str, Any]]],
              *, our_mode: Optional[str] = None) -> dict[str, Any]:
    """What the registry and the docker daemon say, reconciled into actions.

    ``rows`` are session rows from the registry (``None`` = unreadable);
    ``containers`` are ``{"name": str, "mode": str|None}`` from ``docker ps``
    (``None`` = docker unreadable). The result carries its OWN DOMAIN — how many
    rows and how many containers it compared — because a reconciliation that
    reports "0 orphans" without saying what it compared is a null result with no
    domain, and this fund has shipped two of those.

    NOTHING IS DECIDED UNLESS BOTH SIDES WERE READ. An unreadable docker daemon
    cannot prove a row's container is gone; an unreadable registry cannot prove
    a container is an orphan. Either one absent and the answer is the empty
    action list WITH ``checked: false`` beside it, never an empty action list
    that looks like agreement.
    """
    rows_readable = rows is not None
    containers_readable = containers is not None
    parsed: list[dict[str, Any]] = []
    if containers_readable:
        for c in containers or ():
            name = (c or {}).get("name") if isinstance(c, dict) else None
            sid = session_id_of(name)
            if sid is None:
                continue
            own = ownership((c or {}).get("mode"), our_mode)
            parsed.append({"container": str(name), "session_id": sid,
                           "ownership": own})

    live_rows = [r for r in (rows or ()) if is_alive(r)] if rows_readable else []
    by_id = {str((r or {}).get("session_id") or ""): r
             for r in (rows or ())} if rows_readable else {}

    actions: list[dict[str, Any]] = []
    if rows_readable and containers_readable:
        seen: set[str] = set()
        for c in parsed:
            sid = c["session_id"]
            seen.add(sid)
            row = by_id.get(sid)
            if not _touchable(c["ownership"]):
                what = LEAVE
            elif row is None:
                what = STOP
            elif is_alive(row):
                what = REATTACH
            else:
                what = ADOPT
            actions.append({**c, "action": what,
                            "row_state": (row or {}).get("state")})
        for r in live_rows:
            sid = str(r.get("session_id") or "")
            if sid and sid not in seen:
                actions.append({"container": r.get("container"),
                                "session_id": sid, "ownership": OWN_OURS,
                                "action": VANISHED,
                                "row_state": r.get("state")})

    counts = {k: sum(1 for a in actions if a["action"] == k)
              for k in (REATTACH, ADOPT, STOP, LEAVE, VANISHED)}
    checked = rows_readable and containers_readable
    return {
        "checked": checked,
        "registry_readable": rows_readable,
        "containers_readable": containers_readable,
        # THE DOMAIN. ``None`` where the side could not be read, so a zero is
        # never mistaken for a comparison that found nothing.
        "rows_seen": len(rows or ()) if rows_readable else None,
        "rows_alive": len(live_rows) if rows_readable else None,
        "containers_seen": len(parsed) if containers_readable else None,
        "our_mode": our_mode,
        "actions": actions,
        "counts": counts,
        "note": reconcile_note(checked, rows_readable, containers_readable,
                               len(parsed) if containers_readable else None,
                               len(live_rows) if rows_readable else None,
                               counts),
    }


def reconcile_note(checked: bool, rows_readable: bool,
                   containers_readable: bool,
                   containers_seen: Optional[int],
                   rows_alive: Optional[int],
                   counts: dict[str, int]) -> str:
    """One sentence, ending in a period because every consumer concatenates it.

    Written here rather than at the caller for the reason the whole module
    exists: the note is one more field of the same multi-field state, and a note
    patched by a caller is the field nobody patches.
    """
    if not containers_readable and not rows_readable:
        return ("Neither the docker daemon nor the session registry could be "
                "read, so nothing was reconciled and no container was judged.")
    if not containers_readable:
        return ("The docker daemon could not be read, so no container was "
                f"judged; the registry holds {rows_alive} session(s) it "
                "believes alive, and whether any of them is still running is "
                "UNKNOWN rather than no.")
    if not rows_readable:
        return (f"The session registry could not be read, so the {containers_seen} "
                "running LEAN container(s) could not be matched to any session "
                "and none was stopped — an unreadable registry proves no orphan.")
    parts = [f"{containers_seen} running LEAN container(s) against "
             f"{rows_alive} session(s) the registry believes alive"]
    for label, key in (("re-attached", REATTACH), ("adopted", ADOPT),
                       ("stopped as unaccounted", STOP),
                       ("left alone (another mode)", LEAVE),
                       ("recorded vanished", VANISHED)):
        if counts.get(key):
            parts.append(f"{counts[key]} {label}")
    return "Reconciled " + "; ".join(parts) + "."


def known_since(registry_required: bool, registry_epoch: Optional[str],
                process_born: Optional[str]) -> Optional[str]:
    """The instant a session record COULD first have existed — the fence's anchor.

    **THE ANCHOR MOVED WHEN THE SESSIONS BECAME DURABLE, AND THE DIRECTION OF
    THE MOVE IS THE WHOLE SAFETY ARGUMENT.** ``engineledger.signal_liveness``
    fences a signal only when it was raised STRICTLY BEFORE this instant, and
    fencing is the permissive direction (a fenced signal stops counting toward
    the divergence verdict). So an EARLIER anchor fences fewer signals and is
    strictly safer; a LATER anchor fences more and is not.

    Three cases, each landing on the safe side of that:

    * **no registry** (no Postgres — every test, and any deployment without
      one): the process's own birth, exactly as before. A memory-only runner
      genuinely cannot hold a record from before it started.
    * **registry readable**: the registry's epoch, which is EARLIER than any
      process birth and therefore fences a strict subset of what memory-birth
      fenced. Sessions now survive restarts, so the honest line is when the
      TABLE began recording, not when this process did.
    * **registry required but its epoch unreadable**: ``None``. NOT the process
      birth — that is the later, more permissive value, and falling back to it
      would silently fence signals the registry might well have accounted for.
      ``None`` makes the fence prove nothing (``BASIS_KNOWN_SINCE_UNREADABLE``),
      which is the direction an unreadable input is required to take.
    """
    if not registry_required:
        return (process_born or "").strip() or None
    epoch = (registry_epoch or "").strip()
    return epoch or None
