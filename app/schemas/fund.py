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
