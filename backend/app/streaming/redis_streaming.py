import asyncio
import json
import redis
import websockets
from typing import Dict, List, Optional, Set
import logzero
import os
from datetime import datetime
from trading.smart_api_manager import SmartAPIManager

logger = logzero.logger


class RedisMarketStreamer:
    """Redis-based real-time market data streaming"""
    
    def __init__(self):
        # Redis connections
        self.redis_host = os.getenv('REDIS_HOST', 'redis')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_client = redis.StrictRedis(
            host=self.redis_host, 
            port=self.redis_port, 
            db=0, 
            decode_responses=True
        )
        self.redis_pubsub = self.redis_client.pubsub()
        
        # SmartAPI connection
        self.smart_api = None
        self.websocket_connection = None
        self.active_tokens: Set[str] = set()
        self.is_streaming = False
        
        # Redis channels
        self.PRICE_CHANNEL = "market:prices"
        self.OI_CHANNEL = "market:oi"
        self.VOLUME_CHANNEL = "market:volume"
        self.SIGNALS_CHANNEL = "trading:signals"
        
    def initialize_smart_api(self, api_key: str, username: str, password: str, totp: str) -> bool:
        """Initialize SmartAPI connection"""
        try:
            self.smart_api = SmartAPIManager(api_key, username, password, totp)
            if self.smart_api.authenticate():
                logger.info("SmartAPI authenticated successfully")
                return True
            else:
                logger.error("SmartAPI authentication failed")
                return False
        except Exception as e:
            logger.error(f"SmartAPI initialization error: {e}")
            return False
    
    def add_streaming_tokens(self, tokens: List[str]):
        """Add tokens for streaming"""
        self.active_tokens.update(tokens)
        logger.info(f"Added {len(tokens)} tokens. Total active: {len(self.active_tokens)}")
    
    def remove_streaming_tokens(self, tokens: List[str]):
        """Remove tokens from streaming"""
        self.active_tokens.difference_update(tokens)
        logger.info(f"Removed {len(tokens)} tokens. Active: {len(self.active_tokens)}")
    
    async def start_streaming(self, tokens: List[str]) -> bool:
        """Start Redis-based streaming"""
        try:
            if not self.smart_api or not self.smart_api.is_authenticated():
                logger.error("SmartAPI not authenticated")
                return False
            
            self.add_streaming_tokens(tokens)
            self.is_streaming = True
            
            # Start WebSocket connection
            asyncio.create_task(self.websocket_stream())
            
            logger.info(f"Started Redis streaming for {len(tokens)} tokens")
            return True
            
        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            return False
    
    async def websocket_stream(self):
        """WebSocket streaming to Redis"""
        try:
            # Mock SmartAPI WebSocket URL (replace with actual)
            ws_url = "wss://smartapisocket.angelone.in/smart-stream"
            
            # For development, simulate data
            await self.simulate_market_data()
            
        except Exception as e:
            logger.error(f"WebSocket streaming error: {e}")
    
    async def simulate_market_data(self):
        """Simulate market data for development"""
        import random
        import time
        
        logger.info("Starting market data simulation...")
        
        # Base prices for simulation
        base_prices = {
            "447552": 5700.0,  # CRUDEOIL futures
            "447849": 280.0    # NATURALGAS futures
        }
        
        while self.is_streaming:
            try:
                for token in self.active_tokens:
                    if token in base_prices:
                        # Simulate price movement
                        base_price = base_prices[token]
                        price_change = random.uniform(-0.5, 0.5)  # ±0.5% change
                        current_price = base_price * (1 + price_change / 100)
                        
                        # Update base price gradually
                        base_prices[token] = current_price
                        
                        # Create market data
                        market_data = {
                            'token': token,
                            'symbol': 'CRUDEOIL21JUL25FUT' if token == '447552' else 'NATURALGAS28JUL25FUT',
                            'ltp': round(current_price, 2),
                            'open': round(current_price * random.uniform(0.995, 1.005), 2),
                            'high': round(current_price * random.uniform(1.001, 1.01), 2),
                            'low': round(current_price * random.uniform(0.99, 0.999), 2),
                            'volume': random.randint(100, 1000),
                            'oi': random.randint(10000, 50000),
                            'oi_change': random.uniform(-5, 5),
                            'change': price_change,
                            'change_percent': round(price_change, 2),
                            'timestamp': datetime.now().isoformat(),
                            'exchange': 'MCX'
                        }
                        
                        # Publish to Redis
                        await self.publish_market_data(market_data)
                
                # Wait before next tick
                await asyncio.sleep(1)  # 1 second interval
                
            except Exception as e:
                logger.error(f"Error in market data simulation: {e}")
                await asyncio.sleep(1)
    
    async def publish_market_data(self, data: Dict):
        """Publish market data to Redis channels"""
        try:
            token = data['token']
            
            # Publish to price channel
            price_data = {
                'token': token,
                'symbol': data['symbol'],
                'ltp': data['ltp'],
                'open': data.get('open'),
                'high': data.get('high'),
                'low': data.get('low'),
                'change': data.get('change', 0),
                'change_percent': data.get('change_percent', 0),
                'timestamp': data['timestamp']
            }
            
            self.redis_client.publish(
                self.PRICE_CHANNEL,
                json.dumps(price_data)
            )
            
            # Cache latest price
            await self.cache_latest_price(token, price_data)
            
            # Publish OI data if available
            if 'oi' in data:
                oi_data = {
                    'token': token,
                    'symbol': data['symbol'],
                    'oi': data['oi'],
                    'oi_change': data.get('oi_change', 0),
                    'timestamp': data['timestamp']
                }
                
                self.redis_client.publish(
                    self.OI_CHANNEL,
                    json.dumps(oi_data)
                )
            
            # Publish volume data if available
            if 'volume' in data:
                volume_data = {
                    'token': token,
                    'symbol': data['symbol'],
                    'volume': data['volume'],
                    'timestamp': data['timestamp']
                }
                
                self.redis_client.publish(
                    self.VOLUME_CHANNEL,
                    json.dumps(volume_data)
                )
            
        except Exception as e:
            logger.error(f"Error publishing market data: {e}")
    
    async def cache_latest_price(self, token: str, price_data: Dict):
        """Cache latest price in Redis"""
        try:
            # Store latest price with expiry
            price_key = f"live_price:{token}"
            self.redis_client.setex(
                price_key, 
                300,  # 5 minutes expiry
                json.dumps(price_data)
            )
            
            # Store in time-series for charts
            ts_key = f"price_series:{token}"
            timestamp = int(datetime.now().timestamp())
            
            # Add to sorted set with timestamp as score
            self.redis_client.zadd(ts_key, {
                json.dumps({
                    'price': price_data['ltp'],
                    'volume': price_data.get('volume', 0),
                    'timestamp': price_data['timestamp']
                }): timestamp
            })
            
            # Keep only last 1000 data points
            self.redis_client.zremrangebyrank(ts_key, 0, -1001)
            
        except Exception as e:
            logger.error(f"Error caching price data: {e}")
    
    def get_latest_price(self, token: str) -> Optional[Dict]:
        """Get latest price from cache"""
        try:
            price_key = f"live_price:{token}"
            data = self.redis_client.get(price_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting latest price: {e}")
            return None
    
    def get_price_series(self, token: str, minutes: int = 60) -> List[Dict]:
        """Get price series for charts"""
        try:
            ts_key = f"price_series:{token}"
            cutoff_time = int(datetime.now().timestamp()) - (minutes * 60)
            
            # Get data from sorted set
            data = self.redis_client.zrangebyscore(
                ts_key, 
                cutoff_time, 
                '+inf', 
                withscores=True
            )
            
            result = []
            for item, score in data:
                try:
                    parsed_item = json.loads(item)
                    result.append(parsed_item)
                except:
                    continue
            
            return result
        except Exception as e:
            logger.error(f"Error getting price series: {e}")
            return []
    
    def publish_signal(self, signal_data: Dict):
        """Publish trading signal"""
        try:
            self.redis_client.publish(
                self.SIGNALS_CHANNEL,
                json.dumps(signal_data)
            )
            
            # Also store in recent signals list
            signals_key = "recent_signals"
            self.redis_client.lpush(signals_key, json.dumps(signal_data))
            self.redis_client.ltrim(signals_key, 0, 99)  # Keep last 100
            
        except Exception as e:
            logger.error(f"Error publishing signal: {e}")
    
    def get_recent_signals(self, count: int = 10) -> List[Dict]:
        """Get recent trading signals"""
        try:
            signals_key = "recent_signals"
            data = self.redis_client.lrange(signals_key, 0, count - 1)
            
            signals = []
            for item in data:
                try:
                    signals.append(json.loads(item))
                except:
                    continue
            
            return signals
        except Exception as e:
            logger.error(f"Error getting recent signals: {e}")
            return []
    
    def stop_streaming(self):
        """Stop streaming"""
        try:
            self.is_streaming = False
            if self.websocket_connection:
                asyncio.create_task(self.websocket_connection.close())
            
            self.active_tokens.clear()
            logger.info("Redis streaming stopped")
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
    
    def get_active_tokens(self) -> List[str]:
        """Get active streaming tokens"""
        return list(self.active_tokens)
    
    def get_streaming_status(self) -> Dict:
        """Get streaming status"""
        return {
            'is_streaming': self.is_streaming,
            'active_tokens': len(self.active_tokens),
            'tokens': list(self.active_tokens),
            'redis_connected': self.redis_client.ping() if self.redis_client else False
        }


# Global instance
redis_streamer = RedisMarketStreamer()
