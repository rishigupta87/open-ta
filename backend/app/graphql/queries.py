import strawberry
from typing import List, Optional
from datetime import datetime
import redis
import json
from .types import MarketData, StreamInfo, HealthStatus, RedisData, TradingStatus, TradingInstrument, InstrumentStats, NearestStrikesResponse, FuturesContract, StrikeData, OptionContract, ActiveStreamingTokens, OISignalResponse, OIAnalyticsResponse, MarketStatusResponse, SignalEngineResponse, OISignalData, OIAnalyticsData, SignalEngineStatus
from ..streaming.service import streamer
from trading.realtime_data_manager import realtime_data_manager
from ..db.operations import get_db, get_instruments_count, get_instruments_by_exchange, get_instruments_by_type, search_instruments, get_instrument_stats
from ..db.models import TradingInstrument as DBTradingInstrument
from ..trading.strike_manager import strike_manager
from ..trading.futures_manager import futures_manager


@strawberry.type
class Query:
    @strawberry.field
    def health(self) -> HealthStatus:
        """Get API health status"""
        return HealthStatus(
            status="healthy",
            timestamp=datetime.now(),
            version="1.0.0"
        )
    
    @strawberry.field
    def market_data(self, symbol: str) -> Optional[MarketData]:
        """Get latest market data for a symbol"""
        try:
            data = realtime_data_manager.get_latest_data(symbol)
            if data:
                return MarketData(
                    symbol=symbol,
                    price=data.get('price', 0.0),
                    volume=data.get('volume', 0),
                    timestamp=datetime.now(),
                    high=data.get('high'),
                    low=data.get('low'),
                    open=data.get('open'),
                    close=data.get('close')
                )
            return None
        except Exception as e:
            print(f"Error fetching market data: {e}")
            return None
    
    @strawberry.field
    def running_streams(self) -> List[StreamInfo]:
        """Get all currently running streams"""
        try:
            streams = []
            for category, info in streamer.active_categories.items():
                streams.append(StreamInfo(
                    category=category,
                    is_active=True,
                    started_at=info.get('started_at', datetime.now()),
                    message_count=info.get('message_count', 0)
                ))
            return streams
        except Exception as e:
            print(f"Error fetching running streams: {e}")
            return []
    
    @strawberry.field
    def redis_data(self) -> List[RedisData]:
        """Get all data from Redis"""
        try:
            redis_client = redis.StrictRedis(host='redis', port=6379, db=0)
            keys = redis_client.keys("websocket-data:*")
            all_data = []
            
            for key in keys:
                key_str = key.decode("utf-8")
                data = redis_client.lrange(key, 0, -1)
                parsed_data = [json.loads(item.decode("utf-8")) for item in data]
                
                all_data.append(RedisData(
                    key=key_str,
                    data=json.dumps(parsed_data),
                    timestamp=datetime.now()
                ))
            
            return all_data
        except Exception as e:
            print(f"Error fetching Redis data: {e}")
            return []
    
    @strawberry.field
    def trading_status(self) -> List[TradingStatus]:
        """Get trading status for all strategies"""
        # This would be implemented when trading functionality is added
        return []
    
    @strawberry.field
    def instruments(
        self, 
        exchange: Optional[str] = None,
        instrument_type: Optional[str] = None,
        limit: int = 100
    ) -> List[TradingInstrument]:
        """Get trading instruments with optional filters"""
        try:
            db = get_db()
            try:
                if exchange and instrument_type:
                    # Get by both exchange and type
                    db_instruments = db.query(DBTradingInstrument).filter(
                        DBTradingInstrument.exch_seg == exchange,
                        DBTradingInstrument.instrumenttype == instrument_type
                    ).limit(limit).all()
                elif exchange:
                    db_instruments = get_instruments_by_exchange(db, exchange)[:limit]
                elif instrument_type:
                    db_instruments = get_instruments_by_type(db, instrument_type)[:limit]
                else:
                    db_instruments = db.query(DBTradingInstrument).limit(limit).all()
                
                # Convert to GraphQL types
                return [
                    TradingInstrument(
                        token=inst.token,
                        symbol=inst.symbol,
                        name=inst.name,
                        expiry=inst.expiry,
                        strike=inst.strike,
                        lotsize=inst.lotsize,
                        instrumenttype=inst.instrumenttype,
                        exch_seg=inst.exch_seg,
                        tick_size=inst.tick_size,
                        created_at=inst.created_at,
                        updated_at=inst.updated_at
                    )
                    for inst in db_instruments
                ]
            finally:
                db.close()
        except Exception as e:
            print(f"Error fetching instruments: {e}")
            return []
    
    @strawberry.field
    def search_instruments(self, query: str, exchange: Optional[str] = None, limit: int = 50) -> List[TradingInstrument]:
        """Search instruments by symbol or name"""
        try:
            db = get_db()
            try:
                db_instruments = search_instruments(db, query, exchange, limit=limit)
                
                return [
                    TradingInstrument(
                        token=inst.token,
                        symbol=inst.symbol,
                        name=inst.name,
                        expiry=inst.expiry,
                        strike=inst.strike,
                        lotsize=inst.lotsize,
                        instrumenttype=inst.instrumenttype,
                        exch_seg=inst.exch_seg,
                        tick_size=inst.tick_size,
                        created_at=inst.created_at,
                        updated_at=inst.updated_at
                    )
                    for inst in db_instruments
                ]
            finally:
                db.close()
        except Exception as e:
            print(f"Error searching instruments: {e}")
            return []
    
    @strawberry.field
    def instrument_stats(self) -> Optional[InstrumentStats]:
        """Get instrument statistics"""
        try:
            db = get_db()
            try:
                stats = get_instrument_stats(db)
                return InstrumentStats(
                    total_instruments=stats["total_instruments"],
                    by_exchange=json.dumps(stats["by_exchange"]),
                    by_type=json.dumps(stats["by_type"])
                )
            finally:
                db.close()
        except Exception as e:
            print(f"Error fetching instrument stats: {e}")
            return None
    
    @strawberry.field
    def nearest_strikes(
        self, 
        futures_token: str, 
        center_price: Optional[float] = None,
        num_strikes: int = 5
    ) -> NearestStrikesResponse:
        """Get nearest strikes around futures price"""
        try:
            # Get nearest strikes data
            strikes_data = strike_manager.find_nearest_strikes(
                futures_token, center_price, num_strikes
            )
            
            if not strikes_data:
                return NearestStrikesResponse(
                    success=False,
                    message="No strikes data found for the given futures token"
                )
            
            # Convert to GraphQL types
            futures_contract = None
            if "futures" in strikes_data:
                f = strikes_data["futures"]
                futures_contract = FuturesContract(
                    token=f["token"],
                    symbol=f["symbol"],
                    expiry=f["expiry"],
                    lotsize=f["lotsize"]
                )
            
            strikes_list = []
            for strike_info in strikes_data.get("strikes", []):
                call_contract = None
                put_contract = None
                
                if strike_info.get("call"):
                    c = strike_info["call"]
                    call_contract = OptionContract(
                        token=c["token"],
                        symbol=c["symbol"],
                        strike=c["strike"],
                        lotsize=c["lotsize"]
                    )
                
                if strike_info.get("put"):
                    p = strike_info["put"]
                    put_contract = OptionContract(
                        token=p["token"],
                        symbol=p["symbol"],
                        strike=p["strike"],
                        lotsize=p["lotsize"]
                    )
                
                strikes_list.append(StrikeData(
                    strike=strike_info["strike"],
                    call=call_contract,
                    put=put_contract
                ))
            
            # Count total tokens
            all_tokens = strike_manager.get_all_tokens_for_streaming(strikes_data)
            
            return NearestStrikesResponse(
                success=True,
                message=f"Found {len(strikes_list)} nearest strikes",
                futures=futures_contract,
                center_price=strikes_data.get("center_price"),
                strikes=strikes_list,
                total_tokens=len(all_tokens)
            )
            
        except Exception as e:
            return NearestStrikesResponse(
                success=False,
                message=f"Error finding nearest strikes: {str(e)}"
            )
    
    @strawberry.field
    def active_streaming_tokens(self) -> ActiveStreamingTokens:
        """Get all active streaming tokens"""
        try:
            tokens = futures_manager.get_all_active_tokens()
            
            return ActiveStreamingTokens(
                success=True,
                message=f"Found {len(tokens)} active streaming tokens",
                tokens=tokens,
                count=len(tokens)
            )
            
        except Exception as e:
            return ActiveStreamingTokens(
                success=False,
                message=f"Error getting active tokens: {str(e)}",
                tokens=[],
                count=0
            )
    
    @strawberry.field
    def get_oi_signals(
        self, 
        limit: int = 50,
        signal_strength: Optional[str] = None,
        underlying: Optional[str] = None,
        exchange: Optional[str] = None
    ) -> OISignalResponse:
        """Get latest OI signals with filtering"""
        try:
            from ..db.models import OISignal
            from ..signals.oi_signal_engine import oi_signal_engine
            from sqlalchemy import desc, and_
            
            db = get_db()
            try:
                # Build query with filters
                query = db.query(OISignal)
                
                filters = []
                if signal_strength:
                    filters.append(OISignal.signal_strength == signal_strength)
                if underlying:
                    filters.append(OISignal.underlying == underlying)
                if exchange:
                    filters.append(OISignal.exchange == exchange)
                
                if filters:
                    query = query.filter(and_(*filters))
                
                # Get signals ordered by timestamp
                signals = query.order_by(desc(OISignal.timestamp)).limit(limit).all()
                
                # Convert to GraphQL types
                signal_data = []
                for signal in signals:
                    signal_data.append(OISignalData(
                        id=signal.id,
                        timestamp=signal.timestamp.isoformat(),
                        token=signal.token,
                        symbol=signal.symbol,
                        current_oi=signal.current_oi or 0,
                        previous_oi=signal.previous_oi or 0,
                        oi_change=signal.oi_change or 0,
                        oi_change_percent=signal.oi_change_percent or 0.0,
                        current_price=signal.current_price or 0.0,
                        implied_volatility=signal.implied_volatility or 0.0,
                        signal_strength=signal.signal_strength or "",
                        signal_type=signal.signal_type or "",
                        exchange=signal.exchange or "",
                        instrument_type=signal.instrument_type or "",
                        underlying=signal.underlying or "",
                        strike_price=signal.strike_price,
                        option_type=signal.option_type or "",
                        analysis_window=signal.analysis_window or "5m"
                    ))
                
                return OISignalResponse(
                    success=True,
                    message=f"Retrieved {len(signal_data)} OI signals",
                    signals=signal_data,
                    total_count=len(signal_data)
                )
                
            finally:
                db.close()
                
        except Exception as e:
            return OISignalResponse(
                success=False,
                message=f"Error getting OI signals: {str(e)}",
                signals=[],
                total_count=0
            )
    
    @strawberry.field
    def get_oi_analytics(
        self, 
        limit: int = 10,
        underlying: Optional[str] = None
    ) -> OIAnalyticsResponse:
        """Get latest OI analytics"""
        try:
            from ..db.models import OIAnalytics
            from sqlalchemy import desc, and_
            
            db = get_db()
            try:
                query = db.query(OIAnalytics)
                
                if underlying:
                    query = query.filter(OIAnalytics.underlying == underlying)
                
                analytics = query.order_by(desc(OIAnalytics.timestamp)).limit(limit).all()
                
                analytics_data = []
                for analytic in analytics:
                    analytics_data.append(OIAnalyticsData(
                        id=analytic.id,
                        timestamp=analytic.timestamp.isoformat(),
                        underlying=analytic.underlying,
                        total_oi_change=analytic.total_oi_change or 0,
                        total_oi_change_percent=analytic.total_oi_change_percent or 0.0,
                        call_oi_change=analytic.call_oi_change or 0,
                        put_oi_change=analytic.put_oi_change or 0,
                        max_call_oi_change=analytic.max_call_oi_change or 0,
                        max_put_oi_change=analytic.max_put_oi_change or 0,
                        max_call_oi_token=analytic.max_call_oi_token or "",
                        max_put_oi_token=analytic.max_put_oi_token or "",
                        avg_iv=analytic.avg_iv or 0.0,
                        max_iv=analytic.max_iv or 0.0,
                        high_iv_count=analytic.high_iv_count or 0,
                        pcr_oi=analytic.pcr_oi or 0.0,
                        market_sentiment=analytic.market_sentiment or "",
                        sentiment_score=analytic.sentiment_score or 0.0,
                        exchange=analytic.exchange or "",
                        session_type=analytic.session_type or ""
                    ))
                
                return OIAnalyticsResponse(
                    success=True,
                    message=f"Retrieved {len(analytics_data)} analytics records",
                    analytics=analytics_data,
                    total_count=len(analytics_data)
                )
                
            finally:
                db.close()
                
        except Exception as e:
            return OIAnalyticsResponse(
                success=False,
                message=f"Error getting OI analytics: {str(e)}",
                analytics=[],
                total_count=0
            )
    
    @strawberry.field
    def get_market_status(self) -> MarketStatusResponse:
        """Get current market status and trading hours"""
        try:
            from ..signals.oi_signal_engine import oi_signal_engine
            
            # Get detailed market status including weekday info
            status = oi_signal_engine.get_detailed_market_status()
            
            return MarketStatusResponse(
                success=True,
                message="Market status retrieved successfully",
                active_exchanges=status['active_exchanges'],
                trading_hours=str(status['trading_hours']),
                current_time_ist=status['current_time_ist'],
                current_day=status['current_day'],
                is_trading_day=status['is_trading_day'],
                is_any_market_open=status['is_any_market_open'],
                status_reason=status['status_reason'],
                next_trading_day=status['next_trading_day'],
                days_until_next_trading=status['days_until_next_trading']
            )
            
        except Exception as e:
            return MarketStatusResponse(
                success=False,
                message=f"Error getting market status: {str(e)}",
                active_exchanges=[],
                trading_hours="",
                current_time_ist="",
                current_day="Unknown",
                is_trading_day=False,
                is_any_market_open=False,
                status_reason=f"Error: {str(e)}",
                next_trading_day="Unknown",
                days_until_next_trading=0
            )
    
    @strawberry.field
    def get_signal_engine_status(self) -> SignalEngineResponse:
        """Get OI signal engine status"""
        try:
            from ..signals.oi_signal_engine import oi_signal_engine
            
            status = SignalEngineStatus(
                is_running=oi_signal_engine.is_running,
                active_exchanges=oi_signal_engine.get_active_exchanges(),
                current_signals_count=len(oi_signal_engine.get_current_signals()),
                last_analysis_time=datetime.utcnow().isoformat(),
                analysis_interval="5m"
            )
            
            return SignalEngineResponse(
                success=True,
                message="Signal engine status retrieved",
                status=status
            )
            
        except Exception as e:
            return SignalEngineResponse(
                success=False,
                message=f"Error getting signal engine status: {str(e)}",
                status=None
            )
    
    @strawberry.field
    def get_current_signals(self, limit: int = 10) -> OISignalResponse:
        """Get current real-time signals from memory"""
        try:
            from ..signals.oi_signal_engine import oi_signal_engine
            
            current_signals = oi_signal_engine.get_current_signals(limit)
            
            signal_data = []
            for signal in current_signals:
                signal_data.append(OISignalData(
                    id=0,  # Memory signals don't have DB IDs
                    timestamp=signal['timestamp'].isoformat(),
                    token=signal['token'],
                    symbol=signal['symbol'],
                    current_oi=signal['current_oi'],
                    previous_oi=signal['previous_oi'],
                    oi_change=signal['oi_change'],
                    oi_change_percent=signal['oi_change_percent'],
                    current_price=signal['current_price'],
                    implied_volatility=signal['implied_volatility'],
                    signal_strength=signal['signal_strength'],
                    signal_type=signal['signal_type'],
                    exchange=signal['exchange'],
                    instrument_type=signal['instrument_type'],
                    underlying=signal['underlying'],
                    strike_price=signal.get('strike_price'),
                    option_type=signal['option_type'],
                    analysis_window=signal['analysis_window']
                ))
            
            return OISignalResponse(
                success=True,
                message=f"Retrieved {len(signal_data)} current signals",
                signals=signal_data,
                total_count=len(signal_data)
            )
            
        except Exception as e:
            return OISignalResponse(
                success=False,
                message=f"Error getting current signals: {str(e)}",
                signals=[],
                total_count=0
            )
