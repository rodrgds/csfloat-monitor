from typing import Optional
from pydantic import BaseModel


class Item(BaseModel):
    market_hash_name: str
    float_value: Optional[float] = None
    paint_seed: Optional[int] = None


class Reference(BaseModel):
    base_price: Optional[float] = None
    predicted_price: Optional[float] = None

    def get_valid_price(self) -> Optional[float]:
        return self.base_price or self.predicted_price


class Listing(BaseModel):
    id: str
    price: int
    type: str
    item: Item
    reference: Optional[Reference] = None

    @property
    def price_usd(self) -> float:
        return self.price / 100.0
