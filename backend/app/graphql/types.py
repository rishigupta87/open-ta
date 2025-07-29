import strawberry
from typing import List, Optional
from datetime import datetime


@strawberry.type
class MarketData:
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    close: Optional[float] = None


@strawberry.type
class StreamInfo:
    category: str
    is_active: bool
    started_at: datetime
    message_count: int


@strawberry.type
class HealthStatus:
    status: str
    timestamp: datetime
    version: str = "1.0.0"


@strawberry.type
class RedisData:
    key: str
    data: str
    timestamp: datetime


@strawberry.type
class TradingStatus:
    strategy_name: str
    is_active: bool
    pnl: float
    positions: str
    total_trades: int


@strawberry.type
class StreamingResponse:
    success: bool
    message: str
    category: Optional[str] = None


@strawberry.type
class InitializationResponse:
    success: bool
    message: str


@strawberry.type
class DataResponse:
    success: bool
    message: str
    data: Optional[str] = None


@strawberry.type
class TradingInstrument:
    token: str
    symbol: str
    name: str
    expiry: Optional[str] = None
    strike: Optional[float] = None
    lotsize: int
    instrumenttype: str
    exch_seg: str
    tick_size: float
    created_at: datetime
    updated_at: datetime


@strawberry.type
class InstrumentStats:
    total_instruments: int
    by_exchange: str  # JSON string of exchange counts
    by_type: str      # JSON string of type counts


@strawberry.type
class InstrumentSyncResponse:
    success: bool
    message: str
    stats: Optional[InstrumentStats] = None
    inserted: int = 0
    updated: int = 0
    errors: int = 0


@strawberry.type
class InstrumentCleanupResponse:
    success: bool
    message: str
    initial_count: int = 0
    final_count: int = 0
    deleted_count: int = 0


@strawberry.type
class OptionContract:
    token: str
    symbol: str
    strike: float
    lotsize: int


@strawberry.type
class StrikeData:
    strike: float
    call: Optional[OptionContract] = None
    put: Optional[OptionContract] = None


@strawberry.type
class FuturesContract:
    token: str
    symbol: str
    expiry: str
    lotsize: int


@strawberry.type
class NearestStrikesResponse:
    success: bool
    message: str
    futures: Optional[FuturesContract] = None
    center_price: Optional[float] = None
    strikes: List[StrikeData] = strawberry.field(default_factory=list)
    total_tokens: int = 0


@strawberry.type
class TokenStorageResponse:
    success: bool
    message: str
    strategy_name: str
    token_count: int = 0


@strawberry.type
class CommodityFutures:
    token: str
    symbol: str
    name: str
    expiry: str
    lotsize: int
    exchange: str
    updated_at: datetime


@strawberry.type
class CommodityStreamingResponse:
    success: bool
    message: str
    commodity: str = ""
    futures: Optional[CommodityFutures] = None
    streaming_token: str = ""


@strawberry.type
class ActiveStreamingTokens:
    success: bool
    message: str
    tokens: List[str] = strawberry.field(default_factory=list)
    count: int = 0


@strawberry.type
class OISignalData:
    id: int
    timestamp: str
    token: str
    symbol: str
    current_oi: int
    previous_oi: int
    oi_change: int
    oi_change_percent: float
    current_price: float
    implied_volatility: float
    signal_strength: str
    signal_type: str
    exchange: str
    instrument_type: str
    underlying: str
    strike_price: Optional[float] = None
    option_type: str = ""
    analysis_window: str = "5m"


@strawberry.type
class OIAnalyticsData:
    id: int
    timestamp: str
    underlying: str
    total_oi_change: int
    total_oi_change_percent: float
    call_oi_change: int
    put_oi_change: int
    max_call_oi_change: int
    max_put_oi_change: int
    max_call_oi_token: str
    max_put_oi_token: str
    avg_iv: float
    max_iv: float
    high_iv_count: int
    pcr_oi: float
    market_sentiment: str
    sentiment_score: float
    exchange: str
    session_type: str


@strawberry.type
class OISignalResponse:
    success: bool
    message: str
    signals: List[OISignalData]
    total_count: int


@strawberry.type
class OIAnalyticsResponse:
    success: bool
    message: str
    analytics: List[OIAnalyticsData]
    total_count: int


@strawberry.type
class MarketStatusResponse:
    success: bool
    message: str
    active_exchanges: List[str]
    trading_hours: str
    current_time_ist: str
    current_day: str
    is_trading_day: bool
    is_any_market_open: bool
    status_reason: str
    next_trading_day: str
    days_until_next_trading: int


@strawberry.type
class SignalEngineStatus:
    is_running: bool
    active_exchanges: List[str]
    current_signals_count: int
    last_analysis_time: Optional[str] = None
    analysis_interval: str = "5m"


@strawberry.type
class SignalEngineResponse:
    success: bool
    message: str
    status: Optional[SignalEngineStatus] = None
