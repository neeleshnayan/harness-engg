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
    thesis_id: Optional[str] = Field(None, description="Investment thesis this order acts on")
    discretionary: bool = Field(False, description="Explicitly a discretionary trade (no thesis)")


class ThesisCreateRequest(BaseModel):
    title: str = Field(..., description="Short name for the idea")
    claim: Optional[str] = Field(None, description="The falsifiable claim, e.g. 'AAPL revisions improve over 3-6mo'")
    assets: Optional[list[str]] = Field(None, description="Symbols the thesis is about")
    strategy_id: Optional[str] = Field(None, description="Linked strategy (systematic edge)")
    owner: Optional[str] = Field(None, description="Who owns the thesis (default the actor)")
    horizon: Optional[str] = Field(None, description="Expected holding horizon")
    entry_rationale: Optional[str] = Field(None, description="Why now / expected catalyst")
    key_risks: Optional[list[str]] = Field(None, description="What could go wrong")
    invalidation_conditions: Optional[list[str]] = Field(None, description="What would falsify this")
    target_exposure_pct: Optional[float] = Field(None, description="Target exposure as % of NAV")
    review_cadence: Optional[str] = Field(None, description="How often to review")
    evidence_ids: Optional[list[str]] = Field(None, description="Linked evidence object ids")
    memo_ids: Optional[list[str]] = Field(None, description="Linked memo ids")
    actor: str = Field("operator", description="Who created it")


class ThesisUpdateRequest(BaseModel):
    patch: dict = Field(..., description="Partial thesis fields to update")
    actor: str = Field("operator", description="Who updated it")


class ThesisStatusRequest(BaseModel):
    status: Literal["draft", "active", "invalidated", "exited", "reviewed"]
    note: Optional[str] = Field(None, description="Why the status changed")
    actor: str = Field("operator", description="Who changed it")


class MemoCreateRequest(BaseModel):
    thesis_id: str = Field(..., description="The thesis this memo argues the case for")
    title: str = Field(..., description="Memo headline, e.g. 'Long AAPL into the print'")
    recommendation: Optional[str] = Field(None, description="The ask, e.g. 'Buy 2% NAV of AAPL'")
    conviction: Optional[Literal["low", "medium", "high"]] = Field(None, description="Conviction level")
    summary: Optional[str] = Field(None, description="One-paragraph thesis-in-brief")
    sections: Optional[dict] = Field(None, description="Ordered {heading: markdown} body sections")
    sources: Optional[list[str]] = Field(None, description="Evidence / source references")
    author: Optional[str] = Field(None, description="Who drafted it (default the actor, e.g. 'clark')")
    actor: str = Field("operator", description="Who created it")


class MemoUpdateRequest(BaseModel):
    patch: dict = Field(..., description="Partial memo fields to update")
    actor: str = Field("operator", description="Who updated it")


class MemoFinalizeRequest(BaseModel):
    actor: str = Field("operator", description="Who signed off on the memo")


class RiskShockRequest(BaseModel):
    symbol: Optional[str] = Field(None, description="Symbol to shock; None => whole book")
    pct: float = Field(..., ge=-99, le=99, description="Percent move to apply, e.g. -20")


class PostmortemRequest(BaseModel):
    verdict: Literal["correct", "partially_correct", "wrong", "invalidated", "too_early"]
    what_happened: Optional[str] = Field(None, description="Narrative of how it played out")
    lessons: Optional[list[str]] = Field(None, description="What we learned for next time")
    actor: str = Field("operator", description="Who recorded the post-mortem")


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
