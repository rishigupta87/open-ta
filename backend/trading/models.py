from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class TradingSymbol:
    """Represents a trading symbol"""
    symbol: str
    token: str
    exchange: str
    lot_size: int = 1
    tick_size: float = 0.01
    
    def __str__(self):
        return f"{self.symbol}:{self.token}:{self.exchange}"


@dataclass
class MarketPrice:
    """Represents market price data"""
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    close: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'price': self.price,
            'volume': self.volume,
            'timestamp': self.timestamp.isoformat(),
            'high': self.high,
            'low': self.low,
            'open': self.open,
            'close': self.close,
            'change': self.change,
            'change_percent': self.change_percent
        }


@dataclass
class Order:
    """Represents a trading order"""
    symbol: str
    order_type: str  # 'BUY' or 'SELL'
    quantity: int
    price: float
    order_id: Optional[str] = None
    status: str = 'PENDING'
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class Position:
    """Represents a trading position"""
    symbol: str
    quantity: int
    average_price: float
    current_price: float
    pnl: float
    pnl_percent: float
    side: str  # 'LONG' or 'SHORT'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'average_price': self.average_price,
            'current_price': self.current_price,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'side': self.side
        }
