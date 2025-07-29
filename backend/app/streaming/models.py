import strawberry
from typing import List, Optional, Dict, Any

@strawberry.type
class StreamingStatus:
    category: str
    streaming: bool
    status: str

@strawberry.type
class TokenInfo:
    name: str
    token: str
    expiry: str

@strawberry.type
class MarketData:
    exchange_timestamp: str
    last_traded_price: float
    last_traded_quantity: int
    average_traded_price: float
    volume_trade_for_the_day: int
    total_buy_quantity: int
    total_sell_quantity: int
    open_price_of_the_day: float
    high_price_of_the_day: float
    low_price_of_the_day: float
    closed_price: float
    last_traded_timestamp: str
    open_interest: int
    open_interest_change_percentage: float

@strawberry.type
class RedisData:
    key: str
    data: List[MarketData]