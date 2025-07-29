import strawberry
from typing import Optional
import redis
import threading
import json
from .types import StreamingResponse, InitializationResponse, DataResponse, InstrumentSyncResponse, InstrumentStats, InstrumentCleanupResponse, TokenStorageResponse, CommodityStreamingResponse, CommodityFutures, SignalEngineResponse
from ..streaming.service import streamer
from ..streaming.market_data_streamer import enhanced_streamer
from trading.smart_api_manager import SmartAPIManager
from ..db.operations import get_db, fetch_instruments_from_api, bulk_upsert_instruments, get_instrument_stats, create_tables, cleanup_instruments
from ..trading.strike_manager import strike_manager
from ..trading.futures_manager import futures_manager
from ..streaming.kafka_producer import market_data_producer
from ..signals.signal_engine import signal_engine


# Global variables for trading state
smart_api_manager = None
active_streams = {}


@strawberry.type
class Mutation:
    @strawberry.mutation
    def start_streaming(self, category: str) -> StreamingResponse:
        """Start streaming for a category"""
        try:
            if category in active_streams:
                return StreamingResponse(
                    success=False,
                    message=f"Streaming already running for {category}",
                    category=category
                )
            
            # Start streaming in a separate thread
            stream_thread = threading.Thread(
                target=streamer.start_streaming, 
                args=(category,)
            )
            stream_thread.start()
            active_streams[category] = stream_thread
            
            return StreamingResponse(
                success=True,
                message=f"Streaming started for {category}",
                category=category
            )
        except Exception as e:
            return StreamingResponse(
                success=False,
                message=f"Failed to start streaming: {str(e)}",
                category=category
            )
    
    @strawberry.mutation
    def stop_streaming(self, category: str) -> StreamingResponse:
        """Stop streaming for a category"""
        try:
            if category not in active_streams:
                return StreamingResponse(
                    success=False,
                    message=f"No streaming running for {category}",
                    category=category
                )
            
            streamer.stop_streaming(category)
            active_streams[category].join()
            del active_streams[category]
            
            return StreamingResponse(
                success=True,
                message=f"Streaming stopped for {category}",
                category=category
            )
        except Exception as e:
            return StreamingResponse(
                success=False,
                message=f"Failed to stop streaming: {str(e)}",
                category=category
            )
    
    @strawberry.mutation
    async def start_enhanced_streaming(self, category: str = "filtered_trading") -> StreamingResponse:
        """Start enhanced market data streaming with TimescaleDB storage"""
        try:
            if enhanced_streamer.is_streaming(category):
                return StreamingResponse(
                    success=False,
                    message=f"Enhanced streaming already running for {category}",
                    category=category
                )
            
            # Start enhanced streaming
            success = await enhanced_streamer.start_market_data_streaming(category)
            
            if success:
                return StreamingResponse(
                    success=True,
                    message=f"Enhanced streaming started for {category}",
                    category=category
                )
            else:
                return StreamingResponse(
                    success=False,
                    message=f"Failed to start enhanced streaming for {category}",
                    category=category
                )
                
        except Exception as e:
            return StreamingResponse(
                success=False,
                message=f"Failed to start enhanced streaming: {str(e)}",
                category=category
            )
    
    @strawberry.mutation
    def stop_enhanced_streaming(self, category: str = "filtered_trading") -> StreamingResponse:
        """Stop enhanced market data streaming"""
        try:
            if not enhanced_streamer.is_streaming(category):
                return StreamingResponse(
                    success=False,
                    message=f"No enhanced streaming for {category}",
                    category=category
                )
            
            success = enhanced_streamer.stop_market_data_streaming(category)
            
            if success:
                return StreamingResponse(
                    success=True,
                    message=f"Enhanced streaming stopped for {category}",
                    category=category
                )
            else:
                return StreamingResponse(
                    success=False,
                    message=f"Failed to stop enhanced streaming for {category}",
                    category=category
                )
                
        except Exception as e:
            return StreamingResponse(
                success=False,
                message=f"Failed to stop enhanced streaming: {str(e)}",
                category=category
            )
    
    @strawberry.mutation
    def initialize_trading(
        self, 
        api_key: str, 
        username: str, 
        password: str, 
        totp_token: str
    ) -> InitializationResponse:
        """Initialize trading with API credentials"""
        global smart_api_manager
        
        try:
            smart_api_manager = SmartAPIManager(api_key, username, password, totp_token)
            if smart_api_manager.authenticate():
                return InitializationResponse(
                    success=True,
                    message="Trading initialized successfully"
                )
            else:
                return InitializationResponse(
                    success=False,
                    message="Authentication failed"
                )
        except Exception as e:
            return InitializationResponse(
                success=False,
                message=f"Initialization failed: {str(e)}"
            )
    
    @strawberry.mutation
    def flush_redis_data(self) -> DataResponse:
        """Flush all data from Redis"""
        try:
            redis_client = redis.StrictRedis(host='redis', port=6379, db=0)
            redis_client.flushdb()
            return DataResponse(
                success=True,
                message="Redis data flushed successfully"
            )
        except Exception as e:
            return DataResponse(
                success=False,
                message=f"Failed to flush Redis data: {str(e)}"
            )
    
    @strawberry.mutation
    def start_strategy(
        self, 
        strategy_name: str, 
        symbols: str, 
        capital: Optional[float] = 100000
    ) -> InitializationResponse:
        """Start a trading strategy"""
        # This would be implemented when trading functionality is added
        return InitializationResponse(
            success=False,
            message="Strategy functionality not implemented yet"
        )
    
    @strawberry.mutation
    def stop_strategy(self, strategy_name: str) -> InitializationResponse:
        """Stop a trading strategy"""
        # This would be implemented when trading functionality is added
        return InitializationResponse(
            success=False,
            message="Strategy functionality not implemented yet"
        )
    
    @strawberry.mutation
    def sync_instruments(self, force_refresh: bool = False) -> InstrumentSyncResponse:
        """Sync trading instruments from AngelOne API to PostgreSQL"""
        try:
            # Create tables if they don't exist
            create_tables()
            
            # Fetch instruments from API
            instruments_data = fetch_instruments_from_api()
            
            if not instruments_data:
                return InstrumentSyncResponse(
                    success=False,
                    message="No instrument data received from API"
                )
            
            # Get database session
            db = get_db()
            try:
                # Bulk upsert instruments
                sync_stats = bulk_upsert_instruments(db, instruments_data)
                
                # Get updated statistics
                db_stats = get_instrument_stats(db)
                
                return InstrumentSyncResponse(
                    success=True,
                    message=f"Successfully synced {len(instruments_data)} instruments",
                    stats=InstrumentStats(
                        total_instruments=db_stats["total_instruments"],
                        by_exchange=json.dumps(db_stats["by_exchange"]),
                        by_type=json.dumps(db_stats["by_type"])
                    ),
                    inserted=sync_stats["inserted"],
                    updated=sync_stats["updated"],
                    errors=sync_stats["errors"]
                )
            finally:
                db.close()
                
        except Exception as e:
            return InstrumentSyncResponse(
                success=False,
                message=f"Failed to sync instruments: {str(e)}",
                inserted=0,
                updated=0,
                errors=0
            )
    
    @strawberry.mutation
    def cleanup_instruments_data(self) -> InstrumentCleanupResponse:
        """Clean up database to keep only NSE, NFO, and MCX crude oil/natural gas instruments"""
        try:
            # Get database session
            db = get_db()
            try:
                # Perform cleanup
                cleanup_stats = cleanup_instruments(db)
                
                return InstrumentCleanupResponse(
                    success=True,
                    message=f"Successfully cleaned up instruments: {cleanup_stats['deleted_count']} deleted",
                    initial_count=cleanup_stats["initial_count"],
                    final_count=cleanup_stats["final_count"],
                    deleted_count=cleanup_stats["deleted_count"]
                )
            finally:
                db.close()
                
        except Exception as e:
            return InstrumentCleanupResponse(
                success=False,
                message=f"Failed to cleanup instruments: {str(e)}",
                initial_count=0,
                final_count=0,
                deleted_count=0
            )
    
    @strawberry.mutation
    def setup_crude_oil_strategy(
        self, 
        strategy_name: str = "crude_oil_scalping",
        futures_token: str = "447552",  # Default July futures
        center_price: Optional[float] = None,
        num_strikes: int = 5
    ) -> TokenStorageResponse:
        """Setup crude oil strategy by finding nearest strikes and storing tokens"""
        try:
            # Get nearest strikes
            strikes_data = strike_manager.find_nearest_strikes(
                futures_token, center_price, num_strikes
            )
            
            if not strikes_data:
                return TokenStorageResponse(
                    success=False,
                    message="Could not find strikes data",
                    strategy_name=strategy_name
                )
            
            # Get all tokens for streaming
            all_tokens = strike_manager.get_all_tokens_for_streaming(strikes_data)
            
            # Store tokens for the strategy
            success = strike_manager.store_strategy_tokens(strategy_name, all_tokens)
            
            if success:
                return TokenStorageResponse(
                    success=True,
                    message=f"Successfully setup strategy with {len(all_tokens)} tokens",
                    strategy_name=strategy_name,
                    token_count=len(all_tokens)
                )
            else:
                return TokenStorageResponse(
                    success=False,
                    message="Failed to store strategy tokens",
                    strategy_name=strategy_name
                )
                
        except Exception as e:
            return TokenStorageResponse(
                success=False,
                message=f"Failed to setup strategy: {str(e)}",
                strategy_name=strategy_name
            )
    
    @strawberry.mutation
    def setup_commodity_streaming(self, commodity: str = "CRUDEOIL") -> CommodityStreamingResponse:
        """Setup streaming for current month futures of a commodity"""
        try:
            # Setup commodity streaming
            result = futures_manager.setup_commodity_streaming(commodity)
            
            if result["success"]:
                futures_data = result["futures_data"]
                
                return CommodityStreamingResponse(
                    success=True,
                    message=result["message"],
                    commodity=commodity,
                    futures=CommodityFutures(
                        token=futures_data["token"],
                        symbol=futures_data["symbol"],
                        name=futures_data["name"],
                        expiry=futures_data["expiry"],
                        lotsize=futures_data["lotsize"],
                        exchange=futures_data["exchange"],
                        updated_at=futures_data["updated_at"]
                    ),
                    streaming_token=result["streaming_token"]
                )
            else:
                return CommodityStreamingResponse(
                    success=False,
                    message=result["message"],
                    commodity=commodity
                )
                
        except Exception as e:
            return CommodityStreamingResponse(
                success=False,
                message=f"Failed to setup commodity streaming: {str(e)}",
                commodity=commodity
            )
    
    @strawberry.mutation
    def start_realtime_streaming(
        self,
        api_key: str,
        username: str,
        password: str,
        totp: str
    ) -> InitializationResponse:
        """Start real-time market data streaming and signal generation"""
        try:
            # Initialize SmartAPI
            if not market_data_producer.initialize_smart_api(api_key, username, password, totp):
                return InitializationResponse(
                    success=False,
                    message="Failed to authenticate with SmartAPI"
                )
            
            # Get active streaming tokens
            active_tokens = futures_manager.get_all_active_tokens()
            
            if not active_tokens:
                return InitializationResponse(
                    success=False,
                    message="No active streaming tokens. Setup commodity streaming first."
                )
            
            # Start market data streaming
            if not market_data_producer.start_streaming(active_tokens):
                return InitializationResponse(
                    success=False,
                    message="Failed to start market data streaming"
                )
            
            # Start signal engine
            import asyncio
            asyncio.create_task(signal_engine.start_signal_processing())
            
            return InitializationResponse(
                success=True,
                message=f"Started real-time streaming for {len(active_tokens)} tokens and signal generation"
            )
            
        except Exception as e:
            return InitializationResponse(
                success=False,
                message=f"Failed to start real-time streaming: {str(e)}"
            )
    
    @strawberry.mutation
    def stop_realtime_streaming(self) -> InitializationResponse:
        """Stop real-time streaming and signal generation"""
        try:
            # Stop market data streaming
            market_data_producer.stop_streaming()
            
            # Stop signal engine
            signal_engine.stop()
            
            return InitializationResponse(
                success=True,
                message="Stopped real-time streaming and signal generation"
            )
            
        except Exception as e:
            return InitializationResponse(
                success=False,
                message=f"Failed to stop streaming: {str(e)}"
            )
    
    @strawberry.mutation
    async def start_oi_signal_engine(self) -> SignalEngineResponse:
        """Start the OI signal analysis engine"""
        try:
            from ..signals.oi_signal_engine import oi_signal_engine
            import asyncio
            
            if oi_signal_engine.is_running:
                return SignalEngineResponse(
                    success=False,
                    message="OI signal engine is already running",
                    status=None
                )
            
            # Start the signal engine in background
            asyncio.create_task(oi_signal_engine.run_signal_analysis())
            
            return SignalEngineResponse(
                success=True,
                message="OI signal engine started successfully",
                status=None
            )
            
        except Exception as e:
            return SignalEngineResponse(
                success=False,
                message=f"Failed to start OI signal engine: {str(e)}",
                status=None
            )
    
    @strawberry.mutation
    def stop_oi_signal_engine(self) -> SignalEngineResponse:
        """Stop the OI signal analysis engine"""
        try:
            from ..signals.oi_signal_engine import oi_signal_engine
            
            if not oi_signal_engine.is_running:
                return SignalEngineResponse(
                    success=False,
                    message="OI signal engine is not running",
                    status=None
                )
            
            oi_signal_engine.stop_analysis()
            
            return SignalEngineResponse(
                success=True,
                message="OI signal engine stopped successfully",
                status=None
            )
            
        except Exception as e:
            return SignalEngineResponse(
                success=False,
                message=f"Failed to stop OI signal engine: {str(e)}",
                status=None
            )
    
    @strawberry.mutation
    async def setup_oi_tables(self) -> SignalEngineResponse:
        """Setup TimescaleDB tables for OI signals and analytics"""
        try:
            from ..db.timescale_operations import create_hypertable
            from ..db.models import OISignal, OIAnalytics
            from ..db.database import engine
            from sqlalchemy import text
            
            db = get_db()
            try:
                # Create tables
                OISignal.metadata.create_all(bind=engine)
                OIAnalytics.metadata.create_all(bind=engine)
                
                # Create hypertables
                try:
                    db.execute(text("""
                        SELECT create_hypertable('oi_signals', 'timestamp', 
                                                chunk_time_interval => INTERVAL '1 hour',
                                                if_not_exists => TRUE);
                    """))
                    db.execute(text("""
                        SELECT create_hypertable('oi_analytics', 'timestamp', 
                                                chunk_time_interval => INTERVAL '1 hour',
                                                if_not_exists => TRUE);
                    """))
                    db.commit()
                except Exception as e:
                    # Hypertables might already exist
                    db.rollback()
                    import logzero
                    logzero.logger.info(f"Hypertables might already exist: {e}")
                
                return SignalEngineResponse(
                    success=True,
                    message="OI tables and hypertables created successfully",
                    status=None
                )
                
            finally:
                db.close()
                
        except Exception as e:
            return SignalEngineResponse(
                success=False,
                message=f"Failed to setup OI tables: {str(e)}",
                status=None
            )
    
    @strawberry.mutation
    async def start_oi_data_collection(self, commodity: str = "CRUDEOIL") -> InitializationResponse:
        """Start collecting OI data for crude oil options"""
        try:
            from ..streaming.oi_data_collector import oi_collector
            
            success = await oi_collector.start_oi_collection(commodity)
            
            if success:
                return InitializationResponse(
                    success=True,
                    message=f"Started OI data collection for {commodity} with {len(oi_collector.active_tokens)} tokens"
                )
            else:
                return InitializationResponse(
                    success=False,
                    message=f"Failed to start OI collection for {commodity}"
                )
                
        except Exception as e:
            return InitializationResponse(
                success=False,
                message=f"Error starting OI collection: {str(e)}"
            )

    @strawberry.mutation
    def stop_oi_data_collection(self) -> InitializationResponse:
        """Stop OI data collection"""
        try:
            from ..streaming.oi_data_collector import oi_collector
            oi_collector.running = False
            
            return InitializationResponse(
                success=True,
                message="Stopped OI data collection"
            )
            
        except Exception as e:
            return InitializationResponse(
                success=False,
                message=f"Error stopping OI collection: {str(e)}"
            )

    @strawberry.mutation
    async def get_oi_status(self) -> DataResponse:
        """Get current OI collection status with debug info"""
        try:
            status_data = oi_collector.get_status()
            
            return DataResponse(
                success=True,
                message=f"OI collection status retrieved",
                data=json.dumps(status_data, indent=2)
            )
            
        except Exception as e:
            return DataResponse(
                success=False,
                message=f"Error getting OI status: {str(e)}"
            )

    @strawberry.mutation
    async def generate_oi_report(self, hours_back: int = 24) -> DataResponse:
        """Generate OI analytics report for the last N hours"""
        try:
            db = get_db()
            try:
                from sqlalchemy import text
                
                query = text("""
                    SELECT 
                        DATE_TRUNC('hour', timestamp) as hour,
                        underlying,
                        AVG(total_oi_change) as avg_oi_change,
                        AVG(pcr_oi) as avg_pcr,
                        mode() WITHIN GROUP (ORDER BY market_sentiment) as dominant_sentiment
                    FROM oi_analytics 
                    WHERE timestamp >= NOW() - INTERVAL :hours_back HOUR
                        AND underlying = 'CRUDEOIL'
                    GROUP BY DATE_TRUNC('hour', timestamp), underlying
                    ORDER BY hour DESC
                """)
                
                result = db.execute(query, {"hours_back": hours_back}).fetchall()
                
                report_data = []
                for row in result:
                    report_data.append({
                        "hour": row.hour.isoformat(),
                        "underlying": row.underlying,
                        "avg_oi_change": row.avg_oi_change,
                        "avg_pcr": row.avg_pcr,
                        "sentiment": row.dominant_sentiment
                    })
                
                return DataResponse(
                    success=True,
                    message=f"Generated OI report with {len(report_data)} data points",
                    data=json.dumps(report_data)
                )
                
            finally:
                db.close()
                
        except Exception as e:
            return DataResponse(
                success=False,
                message=f"Failed to generate OI report: {str(e)}"
            )
