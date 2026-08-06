from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProposeOrderRequest(BaseModel):
    symbol: str = Field(..., description="Instrument symbol, e.g. AAPL")
    side: Literal["buy", "sell"]
    qty: float = Field(..., gt=0, description="Quantity in units/shares")
    venue: str = Field("paper", description="Execution venue connector name")
    limit_price: Optional[float] = Field(None, description="None => market order")
    actor: str = Field("operator", description="Who initiated: operator id or 'agent'")


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
