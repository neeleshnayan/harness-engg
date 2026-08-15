import asyncio
import os
import sys

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.firebase import initialize_firebase
initialize_firebase() # Ensure Firebase is initialized
from app.fund.connectors.alpaca import AlpacaConnector
from app.fund.events import EventStore, Event, EventType
from app.fund.money import D

async def main():
    if not os.getenv("ALPACA_API_KEY") or not os.getenv("ALPACA_SECRET_KEY"):
        print("Error: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env")
        sys.exit(1)

    print("Connecting to Alpaca Paper Trading...")
    connector = AlpacaConnector()
    
    try:
        positions = connector.positions()
        # To get the account equity, we need to use the trading client directly
        account = connector._trading().get_account()
        equity = D(account.equity)
    except Exception as e:
        print(f"Failed to fetch from Alpaca: {e}")
        sys.exit(1)

    print(f"Found {len(positions)} open positions. Total Account Equity: ${equity:,.2f}")
    
    store = EventStore()
    
    # 1. Initialize NAV / Cash
    print("Minting initial cash and units...")
    # Give the default system LP the units
    store.append(Event(
        aggregate_id="lp_alpaca_import", aggregate_type="lp",
        type=EventType.CASH_CONFIRMED,
        payload={"amount": float(equity)},
        actor="system"
    ))
    # We assume 1 unit = $1 at inception for simplicity, or just issue equity units
    store.append(Event(
        aggregate_id="fund", aggregate_type="fund",
        type=EventType.UNITS_ISSUED,
        payload={"lp_id": "lp_alpaca_import", "units": float(equity), "nav_per_unit": 1.0},
        actor="system"
    ))

    # 2. Inject Positions
    print("Injecting positions into EventStore...")
    for p in positions:
        print(f" -> Adopting {p.qty} shares of {p.symbol} at ${p.avg_price:,.2f}")
        store.append(Event(
            aggregate_id=f"alpaca_adopt_{p.symbol}_{int(equity)}", aggregate_type="order",
            type=EventType.ORDER_FILLED,
            payload={
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_price": float(p.avg_price),
                "fees": 0.0,
                "venue": "alpaca"
            },
            actor="system"
        ))
        
    print("\nAdoption complete! The Krypton Fund EventStore now matches your Alpaca Portfolio.")

if __name__ == "__main__":
    asyncio.run(main())
