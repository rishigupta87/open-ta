"""Enhanced market data streaming service for TimescaleDB storage"""

import asyncio
import threading
import time
import json
import websockets
import redis
from datetime import datetime
from typing import Dict, Any, List, Optional
import logzero
from sqlalchemy.orm import Session

from ..db.operations import get_db, get_streaming_tokens_for_trading
from ..db.timescale_operations import insert_market_data_batch, create_hypertable
from ..db.models import TradingInstrument
from ..config import ANGELONE_WS_URL, ANGELONE_API_KEY

logger = logzero.logger


class MarketDataStreamer:
    """Enhanced service for real-time market data streaming and storage"""
    
    def __init__(self):
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        self.redis_client = redis.StrictRedis(host='redis', port=6379, db=0)
        self._stop_events: Dict[str, threading.Event] = {}
        self.websocket_connection = None
        self.streaming_tokens: List[str] = []
        self.market_data_buffer: List[Dict[str, Any]] = []
        self.buffer_size = 100  # Batch insert after 100 records
        
    async def initialize_streaming_tokens(self):
        """Initialize streaming tokens from database"""
        try:
            db = get_db()
            try:
                tokens_dict = get_streaming_tokens_for_trading(db)
                
                # Combine all token types into a single list
                all_tokens = []
                all_tokens.extend(tokens_dict.get('futures', []))
                all_tokens.extend(tokens_dict.get('options_ce', []))
                all_tokens.extend(tokens_dict.get('options_pe', []))
                
                self.streaming_tokens = all_tokens
                logger.info(f"Initialized {len(self.streaming_tokens)} tokens for streaming")
                
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error initializing streaming tokens: {e}")
            return False
    
    async def connect_websocket(self):
        """Connect to AngelOne WebSocket for real-time data"""
        try:
            # AngelOne WebSocket connection logic
            # This is a placeholder - implement actual AngelOne WebSocket logic
            logger.info("Connecting to AngelOne WebSocket...")
            
            # For now, simulate connection
            self.websocket_connection = True
            logger.info("WebSocket connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to WebSocket: {e}")
            return False
    
    async def subscribe_to_tokens(self, tokens: List[str]):
        """Subscribe to market data for specific tokens"""
        try:
            if not self.websocket_connection:
                logger.error("WebSocket not connected")
                return False
            
            # Subscribe to tokens - implement AngelOne WebSocket subscription
            logger.info(f"Subscribing to {len(tokens)} tokens")
            
            # Store subscribed tokens
            self.streaming_tokens = tokens
            
            return True
            
        except Exception as e:
            logger.error(f"Error subscribing to tokens: {e}")
            return False
    
    def simulate_market_data(self, token: str) -> Dict[str, Any]:
        """Simulate market data for testing (replace with actual WebSocket data)"""
        import random
        
        base_price = random.uniform(100, 5000)
        
        return {
            'token': token,
            'symbol': f'SYM_{token}',
            'timestamp': datetime.utcnow(),
            'ltp': round(base_price + random.uniform(-10, 10), 2),
            'open_price': round(base_price, 2),
            'high_price': round(base_price + random.uniform(0, 20), 2),
            'low_price': round(base_price - random.uniform(0, 15), 2),
            'close_price': round(base_price + random.uniform(-5, 5), 2),
            'volume': random.randint(1000, 100000),
            'oi': random.randint(10000, 1000000),
            'oi_change': random.randint(-5000, 5000),
            'bid_price': round(base_price - random.uniform(0.1, 2), 2),
            'ask_price': round(base_price + random.uniform(0.1, 2), 2),
            'bid_qty': random.randint(100, 1000),
            'ask_qty': random.randint(100, 1000),
            'exchange': 'NSE',
            'instrument_type': 'OPTIDX'
        }
    
    async def process_market_data(self, raw_data: Dict[str, Any]):
        """Process and store market data"""
        try:
            # Add to buffer
            self.market_data_buffer.append(raw_data)
            
            # Store to Redis for real-time access
            redis_key = f"market_data:{raw_data['token']}:latest"
            self.redis_client.set(redis_key, json.dumps(raw_data, default=str), ex=300)
            
            # Publish to Redis pub/sub for real-time notifications
            self.redis_client.publish('market_data_stream', json.dumps(raw_data, default=str))
            
            # Batch insert to TimescaleDB when buffer is full
            if len(self.market_data_buffer) >= self.buffer_size:
                await self.flush_market_data_buffer()
                
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
    
    async def flush_market_data_buffer(self):
        """Flush buffered market data to TimescaleDB"""
        try:
            if not self.market_data_buffer:
                return
                
            db = get_db()
            try:
                # Ensure hypertable exists
                create_hypertable(db)
                
                # Insert batch data
                inserted_count = insert_market_data_batch(db, self.market_data_buffer)
                logger.info(f"Inserted {inserted_count} market data records to TimescaleDB")
                
                # Clear buffer
                self.market_data_buffer.clear()
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error flushing market data buffer: {e}")
    
    async def start_market_data_streaming(self, category: str = "filtered_trading"):
        """Start enhanced market data streaming"""
        try:
            if category in self.active_streams:
                logger.warning(f"Streaming already active for category: {category}")
                return False
            
            logger.info(f"Starting market data streaming for category: {category}")
            
            # Initialize tokens
            if not await self.initialize_streaming_tokens():
                logger.error("Failed to initialize streaming tokens")
                return False
            
            if not self.streaming_tokens:
                logger.error("No tokens available for streaming")
                return False
            
            # Connect WebSocket
            if not await self.connect_websocket():
                logger.error("Failed to connect WebSocket")
                return False
            
            # Subscribe to tokens
            if not await self.subscribe_to_tokens(self.streaming_tokens):
                logger.error("Failed to subscribe to tokens")
                return False
            
            # Create stop event
            stop_event = threading.Event()
            self._stop_events[category] = stop_event
            
            # Initialize stream info
            self.active_streams[category] = {
                'started_at': datetime.utcnow(),
                'message_count': 0,
                'tokens_count': len(self.streaming_tokens),
                'status': 'active'
            }
            
            # Start streaming loop in background
            asyncio.create_task(self._enhanced_streaming_loop(category, stop_event))
            
            logger.info(f"Market data streaming started for {len(self.streaming_tokens)} tokens")
            return True
            
        except Exception as e:
            logger.error(f"Error starting market data streaming: {e}")
            return False
    
    async def _enhanced_streaming_loop(self, category: str, stop_event: threading.Event):
        """Enhanced streaming loop with TimescaleDB storage"""
        message_count = 0
        
        while not stop_event.is_set():
            try:
                # Process market data for each token
                for token in self.streaming_tokens:
                    if stop_event.is_set():
                        break
                    
                    # Get market data (simulated for now)
                    market_data = self.simulate_market_data(token)
                    
                    # Process and store data
                    await self.process_market_data(market_data)
                    
                    message_count += 1
                
                # Update stream info
                if category in self.active_streams:
                    self.active_streams[category]['message_count'] = message_count
                    self.active_streams[category]['last_update'] = datetime.utcnow()
                
                # Wait before next iteration
                await asyncio.sleep(1)  # Stream every second
                
            except Exception as e:
                logger.error(f"Error in enhanced streaming loop for {category}: {e}")
                await asyncio.sleep(5)  # Wait before retrying
        
        # Flush remaining buffer data before stopping
        await self.flush_market_data_buffer()
        logger.info(f"Enhanced streaming loop stopped for category: {category}")
    
    def stop_market_data_streaming(self, category: str):
        """Stop market data streaming"""
        try:
            if category not in self.active_streams:
                logger.warning(f"No active streaming for category: {category}")
                return False
            
            logger.info(f"Stopping market data streaming for category: {category}")
            
            # Signal stop
            if category in self._stop_events:
                self._stop_events[category].set()
            
            # Clean up
            if category in self.active_streams:
                del self.active_streams[category]
            
            if category in self._stop_events:
                del self._stop_events[category]
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping market data streaming: {e}")
            return False
    
    def get_active_streams(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all active streams"""
        return self.active_streams.copy()
    
    def is_streaming(self, category: str) -> bool:
        """Check if streaming is active for a category"""
        return category in self.active_streams
    
    def get_latest_market_data(self, token: str) -> Optional[Dict[str, Any]]:
        """Get latest market data for a token from Redis"""
        try:
            redis_key = f"market_data:{token}:latest"
            data = self.redis_client.get(redis_key)
            if data:
                return json.loads(data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting latest market data for token {token}: {e}")
            return None


# Global enhanced streamer instance
enhanced_streamer = MarketDataStreamer()
