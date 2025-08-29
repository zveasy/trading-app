from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, validator


class SimpleOrderModel(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL"]
    qty: int = Field(gt=0)
    order_type: Literal["MKT", "LMT"] = "MKT"
    limit_price: float = 0.0
    account: Optional[str] = None
    idempotency_key: Optional[str] = None

    @validator("symbol")
    def sym_upper(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("symbol required")
        return v

    @validator("limit_price")
    def limit_when_lmt(cls, v: float, values):
        if values.get("order_type") == "LMT" and v <= 0:
            raise ValueError("limit_price must be > 0 for LMT")
        return v


class EnvelopeModel(BaseModel):
    version: Literal["v1"]
    correlation_id: str
    msg_type: Literal["SimpleOrder", "CancelReplaceRequest"]
    payload: dict

    @validator("correlation_id")
    def corr_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("correlation_id required")
        return v
