"""Many-to-many strategy composition + CRUD (rename/archive/membership)."""

import pytest

from app.fund.strategies import StrategyError, StrategyService


def test_rename_and_archive(wire):
    svc = StrategyService(store=wire.store)
    s = svc.register("Momentum", actor="r")["strategy_id"]
    assert svc.rename(s, "Momentum v2", actor="r")["name"] == "Momentum v2"
    with pytest.raises(StrategyError):
        svc.rename(s, "  ", actor="r")
    assert svc.archive(s, actor="r")["archived"] is True


def test_strategy_belongs_to_multiple_parents(wire):
    svc = StrategyService(store=wire.store)
    core = svc.register("Core Equity", actor="r")["strategy_id"]
    tactical = svc.register("Tactical", actor="r")["strategy_id"]
    sleeve = svc.register("Momentum sleeve", actor="r")["strategy_id"]
    svc.add_parent(sleeve, core, actor="r")
    svc.add_parent(sleeve, tactical, actor="r")
    parents = svc.get(sleeve)["parents"]
    assert set(parents) == {core, tactical}
    # parent_id back-compat = first parent
    assert svc.get(sleeve)["parent_id"] in {core, tactical}
    # remove one membership
    svc.remove_parent(sleeve, tactical, actor="r")
    assert svc.get(sleeve)["parents"] == [core]


def test_add_parent_is_idempotent_and_guards_cycles(wire):
    svc = StrategyService(store=wire.store)
    a = svc.register("A", actor="r")["strategy_id"]
    b = svc.register("B", actor="r")["strategy_id"]
    svc.add_parent(b, a, actor="r")            # B under A
    svc.add_parent(b, a, actor="r")            # again -> no duplicate
    assert svc.get(b)["parents"] == [a]
    with pytest.raises(StrategyError):
        svc.add_parent(a, b, actor="r")        # A under B would cycle
    with pytest.raises(StrategyError):
        svc.add_parent(a, a, actor="r")        # self-parent
