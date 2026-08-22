"""Building the order path from the mode. One function, no ternary, no fallback.

This replaces the nested ternary at ``app/api/v1/fund.py:151-163`` (4e2d3a1),
which had FOUR branches and reached a simulator on two of them silently:

    AlpacaConnector()  if _real_broker()                    # FUND_REAL_BROKER + a key
    else PaperConnector(...) if _mock_mode()                # USE_FAKE_FIRESTORE
    else AlpacaConnector()   if os.getenv("ALPACA_API_KEY") # a config value as a mode
    else PaperConnector(...)                                # <- THE SHAM

That last branch is the one the CEO named: *"every order needs to route to
alpaca paper account no sham"*. If the key were ever absent, mistyped, or
dropped by a restart that did not carry the environment, orders went to a
SIMULATOR and the book moved as though they were real — no error, no log line,
and nothing visible from outside. A fund that cannot reach its broker must know
it cannot reach its broker.

The PaperConnector itself is NOT the problem and is kept (desk 5cdb161b, on the
CEO's own question — Alpaca trades weekdays only, and routing simulated fills
to a real broker leaves them queued until the open, so the book never moves and
the point of the simulator is lost). What dies is a PRODUCTION PATH that
reaches it by omission.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

from app.fund.mode import (
    ModeError,
    ModeSpec,
    VenueKind,
    assert_connector_permitted,
)

_log = logging.getLogger(__name__)


class VenueUnavailable(ModeError):
    """The mode's venue cannot be constructed. Never downgraded to a simulator."""


def _alpaca_credentials() -> tuple[Optional[str], Optional[str]]:
    return os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")


def build_connector(spec: ModeSpec,
                    live_pricer: Optional[Callable[[str], Optional[float]]] = None,
                    ) -> Any:
    """The connector this mode requires, or an exception. Never a substitute.

    ``live_pricer`` is only consulted for the simulated venue, where fills are
    fake and the prices they fill at are real.
    """
    if spec.venue_kind is VenueKind.SIMULATED:
        from app.fund.connectors.paper import PaperConnector
        conn: Any = PaperConnector(live_pricer=live_pricer)

    elif spec.venue_kind in (VenueKind.ALPACA_PAPER, VenueKind.ALPACA_LIVE):
        key, secret = _alpaca_credentials()
        if not (key and secret):
            # LOUDLY, AT STARTUP. The old code's answer to this state was a
            # PaperConnector and silence.
            raise VenueUnavailable(
                f"mode {spec.mode.value!r} routes orders to Alpaca and "
                f"ALPACA_API_KEY/ALPACA_SECRET_KEY "
                f"{'are both absent' if not (key or secret) else 'are incomplete'}. "
                f"Refusing to construct an order path: the alternative — falling "
                f"back to a simulator — moves the book as though the orders were "
                f"real, with no error and no way to tell from outside."
            )
        from app.fund.connectors.alpaca import AlpacaConnector
        # paper vs live is DERIVED FROM THE MODE, not from ALPACA_PAPER. That
        # variable was a fourth accidental switch: it decided real money while
        # living in the same file as a CORS list, and nothing tied it to the
        # mode the rest of the fund believed it was in.
        conn = AlpacaConnector(paper=(spec.venue_kind is VenueKind.ALPACA_PAPER))

    else:  # pragma: no cover — unreachable while VenueKind has three members
        raise VenueUnavailable(
            f"no connector is defined for venue kind {spec.venue_kind!r}")

    # The incapability check, before anything can place an order through it.
    assert_connector_permitted(spec, conn)
    _log.warning(
        "ORDER PATH: mode=%s venue=%s connector=%s real_money=%s ledger=%s",
        spec.mode.value, spec.venue_label, type(conn).__name__,
        spec.real_money, spec.pg_database)
    return conn
