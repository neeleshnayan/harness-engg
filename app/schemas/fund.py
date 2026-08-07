from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProposeOrderRequest(BaseModel):
    symbol: str = Field(..., description="Instrument symbol, e.g. AAPL")
    side: Literal["buy", "sell"]
    qty: float = Field(..., gt=0, description="Quantity in units/shares")
    venue: str = Field("paper", description="Execution venue connector name")
    limit_price: Optional[float] = Field(None, description="None => market order")
    actor: str = Field("operator", description="Who initiated: operator id or 'agent'")
    strategy_id: Optional[str] = Field(None, description="Tagging strategy; None => discretionary")


class StrategyRegisterRequest(BaseModel):
    name: str = Field(..., description="Human-readable strategy name")
    definition: Optional[dict] = Field(None, description="LEAN algo / params (opaque blob)")
    parent_id: Optional[str] = Field(None, description="Attach under a container strategy (the layered cake)")
    actor: str = Field("operator", description="Who registered it")


class StrategyStateRequest(BaseModel):
    state: Literal["draft", "backtested", "deployed", "paused"]
    actor: str = Field("operator", description="Who changed the state")


class StrategyAllocationRequest(BaseModel):
    target_pct: float = Field(..., ge=0, le=100, description="Target % of NAV for this strategy")
    actor: str = Field("operator", description="Who set the allocation")


class BacktestResultRequest(BaseModel):
    results: dict = Field(..., description="Backtest metrics blob (from the studio / LEAN)")
    actor: str = Field("operator", description="Who recorded the backtest")


StrategyName = Literal["sma", "buy_hold", "rsi", "breakout", "macd", "bollinger",
                       "momentum", "atr_trail"]


class _StrategyParams(BaseModel):
    strategy: StrategyName = Field("sma", description="Built-in template to simulate")
    fast: int = Field(10, gt=0, description="Fast SMA window (sma)")
    slow: int = Field(30, gt=0, description="Slow SMA window (sma)")
    rsi_period: int = Field(14, gt=0, description="RSI lookback (rsi)")
    rsi_low: float = Field(30.0, ge=0, le=100, description="RSI oversold entry (rsi)")
    rsi_high: float = Field(70.0, ge=0, le=100, description="RSI overbought exit (rsi)")
    breakout_lookback: int = Field(20, gt=1, description="Donchian channel window (breakout)")
    macd_fast: int = Field(12, gt=0, description="MACD fast EMA (macd)")
    macd_slow: int = Field(26, gt=0, description="MACD slow EMA (macd)")
    macd_signal: int = Field(9, gt=0, description="MACD signal EMA (macd)")
    boll_period: int = Field(20, gt=1, description="Bollinger window (bollinger)")
    boll_k: float = Field(2.0, gt=0, le=5, description="Bollinger band width in std devs (bollinger)")
    momentum_lookback: int = Field(20, gt=0, description="Momentum lookback (momentum)")
    atr_period: int = Field(14, gt=0, description="ATR window (atr_trail)")
    atr_mult: float = Field(3.0, gt=0, le=10, description="ATR trailing-stop multiple (atr_trail)")
    actor: str = Field("operator", description="Who ran the backtest")


class BacktestRunRequest(_StrategyParams):
    prices: list[float] = Field(..., min_length=2, description="Close prices, oldest first")


class BacktestBySymbolRequest(_StrategyParams):
    symbol: str = Field(..., min_length=1, max_length=6, description="US equity symbol, e.g. AAPL")
    lookback_days: int = Field(365, gt=1, le=2000, description="Trailing calendar days of daily bars")


class ApprovalRequest(BaseModel):
    approver: str = Field(..., description="Who approved/declined (the human in the loop)")


class StrikeNavRequest(BaseModel):
    actor: str = Field("system", description="Who triggered the strike")


class ActorRequest(BaseModel):
    actor: str = Field(..., description="Who is taking the action (the manager)")


class SubscribeRequest(BaseModel):
    lp_id: str = Field(..., description="Stable identifier for the LP")
    usd_amount: float = Field(..., gt=0, description="Amount the LP is investing, in USD")
    lp_name: Optional[str] = Field(None, description="Display name for the LP")
    actor: str = Field("manager", description="Who recorded the subscription")


class RedeemRequest(BaseModel):
    lp_id: str = Field(..., description="LP redeeming units")
    units: Optional[float] = Field(
        None, gt=0, description="Units to redeem; omit to redeem the full holding"
    )
    actor: str = Field("manager", description="Who recorded the redemption")
