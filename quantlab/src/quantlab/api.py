"""api.py — le même pricer, exposé en HTTP/JSON pour un autre front (React, Excel, un autre service)."""

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from quantlab import services

app = FastAPI(title="quantlab API", version="0.1.0")


class Market(BaseModel):
    spot: float | None = Field(None, gt=0, description="Spot du sous-jacent ; absent = marché de référence")
    vol: float | None = Field(None, gt=0, lt=3, description="Volatilité en décimal (0.18 = 18 %)")
    rate: float | None = Field(None, gt=-0.05, lt=0.5)
    div: float | None = Field(None, ge=0, lt=0.5)


class EuropeanSpec(BaseModel):
    type: Literal["european"] = "european"
    underlying: str = "SX5E"
    K: float = Field(gt=0)
    T: float = Field(gt=0, le=30)
    call: bool = True
    notional: float = 1.0


class PriceRequest(BaseModel):
    product: EuropeanSpec
    market: Market = Market()


class PriceResponse(BaseModel):
    valeur: float
    prix_unitaire: float
    prix_pct: float
    cotation: str
    delta: float
    delta_cash_1pct: float
    gamma_cash_1pct: float
    vega_1pt: float
    devise: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/price", response_model=PriceResponse)
def price(req: PriceRequest):
    md = services.make_market(**req.market.model_dump(), underlying=req.product.underlying)
    try:
        return services.price(req.product.model_dump(), md)
    except KeyError as exc:  # sous-jacent inconnu du marché
        raise HTTPException(status_code=422, detail=f"Donnée de marché manquante : {exc}") from exc
