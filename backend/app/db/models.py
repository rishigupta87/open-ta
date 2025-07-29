from sqlalchemy import Column, Integer, Float, String, DateTime, Index, BigInteger, text
from .database import Base
from datetime import datetime


class Data(Base):
    __tablename__ = "data"

    id = Column(Integer, primary_key=True, index=True)
    volume = Column(Float)
    oi_change = Column(Float)
    oi = Column(Float)
    ltp = Column(Float)
    strike_price = Column(Float)
    type = Column(String(255))


class TradingInstrument(Base):
    __tablename__ = "trading_instruments"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    expiry = Column(String, nullable=True)  # Can be empty for stocks/indices
    strike = Column(Float, nullable=True)   # Strike price for options
    lotsize = Column(Integer, nullable=False)
    instrumenttype = Column(String, index=True, nullable=False)  # EQ, OPTIDX, FUTIDX, etc.
    exch_seg = Column(String, index=True, nullable=False)  # NSE, BSE, etc.
    tick_size = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Create composite indexes for better query performance
    __table_args__ = (
        Index('idx_symbol_exchange', 'symbol', 'exch_seg'),
        Index('idx_name_instrumenttype', 'name', 'instrumenttype'),
        Index('idx_instrumenttype_exchange', 'instrumenttype', 'exch_seg'),
    )


class MarketData(Base):
    """TimescaleDB hypertable for real-time market data"""
    __tablename__ = "market_data"

    id = Column(BigInteger, primary_key=True, index=True)
    token = Column(String, index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # OHLCV Data
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float)
    ltp = Column(Float, nullable=False)  # Last Traded Price
    volume = Column(BigInteger)
    
    # Options specific data
    oi = Column(BigInteger)  # Open Interest
    oi_change = Column(BigInteger)  # OI Change
    
    # Market depth (optional)
    bid_price = Column(Float)
    ask_price = Column(Float)
    bid_qty = Column(BigInteger)
    ask_qty = Column(BigInteger)
    
    # Metadata
    exchange = Column(String, index=True)
    instrument_type = Column(String, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # TimescaleDB hypertable configuration
    __table_args__ = (
        Index('idx_token_timestamp', 'token', 'timestamp'),
        Index('idx_symbol_timestamp', 'symbol', 'timestamp'),
        Index('idx_exchange_timestamp', 'exchange', 'timestamp'),
        # TimescaleDB hypertable creation SQL
        {'postgresql_with_oids': False}
    )


class OISignal(Base):
    """TimescaleDB table for OI-based trading signals"""
    __tablename__ = "oi_signals"

    id = Column(BigInteger, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    token = Column(String, index=True, nullable=False)
    symbol = Column(String, index=True, nullable=False)
    
    # OI Analysis Data
    current_oi = Column(BigInteger)
    previous_oi = Column(BigInteger)
    oi_change = Column(BigInteger)
    oi_change_percent = Column(Float)
    
    # Price and Volatility Data
    current_price = Column(Float)
    implied_volatility = Column(Float)
    
    # Signal Classification
    signal_strength = Column(String)  # 'STRONG', 'MEDIUM', 'WEAK'
    signal_type = Column(String)     # 'BULLISH', 'BEARISH', 'NEUTRAL'
    
    # Metadata
    exchange = Column(String, index=True)
    instrument_type = Column(String, index=True)
    underlying = Column(String, index=True)
    strike_price = Column(Float)
    option_type = Column(String)  # 'CE', 'PE', 'FUTURE'
    
    # Analysis Window
    analysis_window = Column(String, default='5m')  # 5m, 15m, 1h
    
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_oi_signals_timestamp', 'timestamp'),
        Index('idx_oi_signals_token_timestamp', 'token', 'timestamp'),
        Index('idx_oi_signals_symbol_timestamp', 'symbol', 'timestamp'),
        Index('idx_oi_signals_strength', 'signal_strength', 'timestamp'),
        Index('idx_oi_signals_underlying', 'underlying', 'timestamp'),
        {'postgresql_with_oids': False}
    )


class OIAnalytics(Base):
    """TimescaleDB table for aggregated OI analytics"""
    __tablename__ = "oi_analytics"

    id = Column(BigInteger, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    underlying = Column(String, index=True, nullable=False)
    
    # Aggregated Data (5-minute buckets)
    total_oi_change = Column(BigInteger)
    total_oi_change_percent = Column(Float)
    
    # Call/Put Analysis
    call_oi_total = Column(BigInteger)
    put_oi_total = Column(BigInteger)
    call_oi_change = Column(BigInteger)
    put_oi_change = Column(BigInteger)
    
    # Max OI Changes
    max_call_oi_change = Column(BigInteger)
    max_put_oi_change = Column(BigInteger)
    max_call_oi_token = Column(String)
    max_put_oi_token = Column(String)
    
    # Volatility Metrics
    avg_iv = Column(Float)
    max_iv = Column(Float)
    high_iv_count = Column(Integer)  # Count of options with IV > 15
    
    # PCR (Put-Call Ratio)
    pcr_oi = Column(Float)
    pcr_volume = Column(Float)
    
    # Market Sentiment
    market_sentiment = Column(String)  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    sentiment_score = Column(Float)    # -1 to 1
    
    # Exchange specific
    exchange = Column(String, index=True)
    session_type = Column(String)  # 'REGULAR', 'PRE_MARKET', 'POST_MARKET'
    
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_oi_analytics_timestamp', 'timestamp'),
        Index('idx_oi_analytics_underlying_timestamp', 'underlying', 'timestamp'),
        Index('idx_oi_analytics_exchange_timestamp', 'exchange', 'timestamp'),
        {'postgresql_with_oids': False}
    )
