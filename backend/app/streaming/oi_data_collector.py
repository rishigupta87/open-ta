import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import and_, text
from ..db.models import MarketData, OIAnalytics
from ..db.operations import get_db
import logzero
import redis

class OIDataCollector:
    """Collect and store OI data for crude oil options"""
    
    def __init__(self):
        self.active_tokens = set()
        self.oi_cache = {}
        self.running = False
        self.commodity = "CRUDEOIL"
        self.error_log = []
        
        # Initialize Redis with error handling
        try:
            self.redis_client = redis.StrictRedis(host='redis', port=6379, db=0, socket_timeout=5)
            self.redis_client.ping()  # Test connection
            logzero.logger.info("Redis connection established")
        except Exception as e:
            logzero.logger.warning(f"Redis connection failed: {e}")
            self.redis_client = None
    
    async def start_oi_collection(self, commodity: str = "CRUDEOIL"):
        """Start collecting OI data for crude oil options"""
        try:
            self.commodity = commodity
            self.error_log = []
            
            logzero.logger.info(f"Starting OI collection for {commodity}")
            
            # Step 1: Test database connection
            db_test = self.test_database_connection()
            if not db_test:
                self.error_log.append("Database connection failed")
                return False
            
            # Step 2: Get commodity tokens
            tokens = await self.get_commodity_option_tokens(commodity)
            if not tokens:
                self.error_log.append(f"No tokens found for {commodity}")
                logzero.logger.error(f"No tokens found for {commodity}")
                
                # Let's try to find what's available
                available_commodities = await self.get_available_commodities()
                logzero.logger.info(f"Available commodities: {available_commodities}")
                
                return False
            
            self.active_tokens = set(tokens)
            self.running = True
            
            logzero.logger.info(f"Starting OI collection for {len(tokens)} {commodity} tokens")
            
            # Step 3: Start collection tasks
            asyncio.create_task(self.collect_realtime_oi())
            asyncio.create_task(self.process_oi_analytics())
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to start OI collection: {e}"
            logzero.logger.error(error_msg)
            self.error_log.append(error_msg)
            return False
    
    def test_database_connection(self) -> bool:
        """Test database connection"""
        try:
            db = get_db()
            try:
                # Simple test query
                result = db.execute(text("SELECT 1")).fetchone()
                logzero.logger.info("Database connection successful")
                return True
            finally:
                db.close()
        except Exception as e:
            logzero.logger.error(f"Database connection failed: {e}")
            return False
    
    async def get_available_commodities(self) -> List[str]:
        """Get list of available commodities for debugging"""
        try:
            db = get_db()
            try:
                from ..db.timescale_models import TradingInstrument
                
                # Get all unique commodity names
                result = db.query(TradingInstrument.name).filter(
                    and_(
                        TradingInstrument.exch_seg == "MCX",
                        TradingInstrument.instrumenttype.in_(["FUTCOM", "OPTFUT"])
                    )
                ).distinct().all()
                
                commodities = [row.name for row in result]
                return commodities
                
            finally:
                db.close()
                
        except Exception as e:
            logzero.logger.error(f"Failed to get available commodities: {e}")
            return []
    
    async def get_commodity_option_tokens(self, commodity: str) -> List[str]:
        """Get all option tokens for a commodity with detailed logging"""
        try:
            db = get_db()
            try:
                from ..db.timescale_models import TradingInstrument
                
                logzero.logger.info(f"Looking for {commodity} instruments...")
                
                # First, let's see what futures we have
                futures_query = db.query(TradingInstrument).filter(
                    and_(
                        TradingInstrument.name == commodity,
                        TradingInstrument.instrumenttype == "FUTCOM",
                        TradingInstrument.exch_seg == "MCX"
                    )
                )
                
                futures_list = futures_query.all()
                logzero.logger.info(f"Found {len(futures_list)} futures for {commodity}")
                
                if not futures_list:
                    # Try alternative names
                    alt_names = ["CRUDEOIL", "CRUDE OIL", "CRUDEOILM"]
                    for alt_name in alt_names:
                        if alt_name != commodity:
                            alt_futures = db.query(TradingInstrument).filter(
                                and_(
                                    TradingInstrument.name == alt_name,
                                    TradingInstrument.instrumenttype == "FUTCOM",
                                    TradingInstrument.exch_seg == "MCX"
                                )
                            ).all()
                            if alt_futures:
                                logzero.logger.info(f"Found futures under alternative name: {alt_name}")
                                futures_list = alt_futures
                                commodity = alt_name  # Update commodity name
                                break
                
                if not futures_list:
                    logzero.logger.error(f"No futures found for {commodity}")
                    return []
                
                # Get the nearest expiry futures
                futures = sorted(futures_list, key=lambda x: x.expiry or "")[0]
                logzero.logger.info(f"Using futures: {futures.symbol} (expiry: {futures.expiry})")
                
                # Get all options for the same expiry
                options_query = db.query(TradingInstrument).filter(
                    and_(
                        TradingInstrument.name == commodity,
                        TradingInstrument.instrumenttype == "OPTFUT",
                        TradingInstrument.expiry == futures.expiry,
                        TradingInstrument.exch_seg == "MCX"
                    )
                )
                
                options = options_query.all()
                logzero.logger.info(f"Found {len(options)} options for {commodity} expiry {futures.expiry}")
                
                if len(options) == 0:
                    # Try without expiry filter
                    options = db.query(TradingInstrument).filter(
                        and_(
                            TradingInstrument.name == commodity,
                            TradingInstrument.instrumenttype == "OPTFUT",
                            TradingInstrument.exch_seg == "MCX"
                        )
                    ).limit(50).all()  # Limit to 50 for testing
                    
                    logzero.logger.info(f"Found {len(options)} options without expiry filter")
                
                tokens = [opt.token for opt in options if opt.token]
                logzero.logger.info(f"Extracted {len(tokens)} valid tokens")
                
                # Log first few tokens for debugging
                if tokens:
                    logzero.logger.info(f"Sample tokens: {tokens[:5]}")
                
                return tokens
                
            finally:
                db.close()
                
        except Exception as e:
            error_msg = f"Failed to get commodity option tokens: {e}"
            logzero.logger.error(error_msg)
            self.error_log.append(error_msg)
            return []
    
    def stop_oi_collection(self):
        """Stop OI data collection"""
        self.running = False
        logzero.logger.info("Stopped OI data collection")
    
    def get_status(self) -> Dict:
        """Get current status and debug info"""
        return {
            "running": self.running,
            "commodity": self.commodity,
            "active_tokens_count": len(self.active_tokens),
            "active_tokens_sample": list(self.active_tokens)[:5],
            "redis_connected": self.redis_client is not None,
            "error_log": self.error_log[-5:],  # Last 5 errors
            "last_updated": datetime.utcnow().isoformat()
        }
    
    async def collect_realtime_oi(self):
        """Collect real-time OI data from Redis/market feed"""
        while self.running:
            try:
                # For now, let's simulate data collection
                await self.simulate_oi_data_collection()
                await asyncio.sleep(10)  # Collect every 10 seconds
                
            except Exception as e:
                logzero.logger.error(f"OI collection error: {e}")
                await asyncio.sleep(30)
    
    async def simulate_oi_data_collection(self):
        """Simulate OI data collection for testing"""
        try:
            db = get_db()
            try:
                records_added = 0
                current_time = datetime.utcnow()
                
                # Create sample data for first few tokens
                sample_tokens = list(self.active_tokens)[:5]  # Just first 5 for testing
                
                for token in sample_tokens:
                    # Simulate market data
                    import random
                    
                    market_record = MarketData(
                        token=token,
                        symbol=f'{self.commodity}_{token}',
                        timestamp=current_time,
                        ltp=random.uniform(5000, 7000),  # Sample crude oil price range
                        oi=random.randint(1000, 10000),
                        oi_change=random.randint(-100, 100),
                        volume=random.randint(100, 1000),
                        exchange="MCX",
                        instrument_type="OPTFUT"
                    )
                    db.add(market_record)
                    records_added += 1
                
                if records_added > 0:
                    db.commit()
                    logzero.logger.info(f"Simulated and stored {records_added} OI records")
                
            finally:
                db.close()
                
        except Exception as e:
            logzero.logger.error(f"Failed to simulate OI data: {e}")
    
    async def process_oi_analytics(self):
        """Process OI data into analytics every 2 minutes"""
        while self.running:
            try:
                await asyncio.sleep(120)  # Every 2 minutes
                await self.generate_oi_analytics()
                
            except Exception as e:
                logzero.logger.error(f"OI analytics error: {e}")
                await asyncio.sleep(60)
    
    async def generate_oi_analytics(self):
        """Generate aggregated OI analytics"""
        db = get_db()
        try:
            # Query recent OI data
            query = text("""
                SELECT 
                    COUNT(*) as record_count,
                    SUM(oi_change) as total_oi_change,
                    AVG(oi) as avg_oi,
                    SUM(volume) as total_volume,
                    AVG(ltp) as avg_price
                FROM market_data 
                WHERE timestamp >= NOW() - INTERVAL '5 minutes'
                    AND exchange = 'MCX'
                    AND token = ANY(:tokens)
            """)
            
            result = db.execute(query, {
                "tokens": list(self.active_tokens)
            }).fetchone()
            
            if result and result.record_count > 0:
                # Store analytics
                analytics = OIAnalytics(
                    timestamp=datetime.utcnow(),
                    underlying=self.commodity,
                    total_oi_change=result.total_oi_change or 0,
                    call_oi_total=int(result.avg_oi or 0),
                    put_oi_total=int(result.avg_oi or 0),
                    market_sentiment="NEUTRAL",  # Simplified for now
                    exchange="MCX"
                )
                db.add(analytics)
                db.commit()
                
                logzero.logger.info(f"Generated OI analytics: {result.record_count} records processed")
            
        except Exception as e:
            db.rollback()
            logzero.logger.error(f"Failed to generate OI analytics: {e}")
        finally:
            db.close()

# Global instance
oi_collector = OIDataCollector()