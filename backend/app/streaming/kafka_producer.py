import json
import asyncio
import websockets
from kafka import KafkaProducer
from typing import Dict, List, Optional
import logzero
import os
from datetime import datetime
from trading.smart_api_manager import SmartAPIManager

logger = logzero.logger


class MarketDataProducer:
    """Kafka producer for real-time market data from SmartAPI"""
    
    def __init__(self):
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.producer = None
        self.smart_api = None
        self.active_tokens = set()
        self.websocket_connection = None
        
    def initialize_kafka(self):
        """Initialize Kafka producer"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3
            )
            logger.info(f"Kafka producer initialized: {self.kafka_servers}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            return False
    
    def initialize_smart_api(self, api_key: str, username: str, password: str, totp: str):
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
        logger.info(f"Added {len(tokens)} tokens for streaming. Total: {len(self.active_tokens)}")
    
    def remove_streaming_tokens(self, tokens: List[str]):
        """Remove tokens from streaming"""
        self.active_tokens.difference_update(tokens)
        logger.info(f"Removed {len(tokens)} tokens. Remaining: {len(self.active_tokens)}")
    
    async def start_websocket_streaming(self):
        """Start WebSocket streaming for market data"""
        if not self.smart_api or not self.smart_api.is_authenticated():
            logger.error("SmartAPI not authenticated")
            return
        
        if not self.active_tokens:
            logger.warning("No tokens to stream")
            return
        
        try:
            # SmartAPI WebSocket URL (example - adjust based on actual API)
            ws_url = "wss://smartapisocket.angelone.in/smart-stream"
            
            async with websockets.connect(ws_url) as websocket:
                self.websocket_connection = websocket
                logger.info("WebSocket connected")
                
                # Subscribe to tokens
                subscribe_message = {
                    "action": "subscribe",
                    "tokens": list(self.active_tokens),
                    "mode": "full"  # Get complete market data
                }
                
                await websocket.send(json.dumps(subscribe_message))
                logger.info(f"Subscribed to {len(self.active_tokens)} tokens")
                
                # Listen for market data
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await self.process_market_data(data)
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        
        except Exception as e:
            logger.error(f"WebSocket streaming error: {e}")
        finally:
            self.websocket_connection = None
    
    async def process_market_data(self, data: Dict):
        """Process incoming market data and publish to Kafka"""
        try:
            # Extract market data fields
            token = data.get('token')
            if not token:
                return
            
            # Determine data type and route to appropriate topic
            if 'ltp' in data:  # Last traded price
                await self.publish_price_data(token, data)
            
            if 'oi' in data:  # Open interest
                await self.publish_oi_data(token, data)
            
            if 'volume' in data:  # Volume data
                await self.publish_volume_data(token, data)
                
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
    
    async def publish_price_data(self, token: str, data: Dict):
        """Publish price data to Kafka"""
        try:
            price_data = {
                'token': token,
                'ltp': data.get('ltp'),
                'open': data.get('open'),
                'high': data.get('high'),
                'low': data.get('low'),
                'close': data.get('close'),
                'change': data.get('change'),
                'change_percent': data.get('change_percent'),
                'timestamp': datetime.now().isoformat(),
                'exchange': data.get('exchange', 'MCX')
            }
            
            # Determine topic based on instrument type
            topic = 'futures.prices' if 'FUT' in data.get('symbol', '') else 'options.prices'
            
            self.producer.send(
                topic,
                key=token,
                value=price_data
            )
            
            # Also cache in Redis for real-time access
            await self.cache_latest_price(token, price_data)
            
        except Exception as e:
            logger.error(f"Error publishing price data: {e}")
    
    async def publish_oi_data(self, token: str, data: Dict):
        """Publish open interest data to Kafka"""
        try:
            oi_data = {
                'token': token,
                'oi': data.get('oi'),
                'oi_change': data.get('oi_change'),
                'oi_percent_change': data.get('oi_percent_change'),
                'timestamp': datetime.now().isoformat(),
                'symbol': data.get('symbol')
            }
            
            self.producer.send(
                'market.oi',
                key=token,
                value=oi_data
            )
            
        except Exception as e:
            logger.error(f"Error publishing OI data: {e}")
    
    async def publish_volume_data(self, token: str, data: Dict):
        """Publish volume data to Kafka"""
        try:
            volume_data = {
                'token': token,
                'volume': data.get('volume'),
                'volume_avg': data.get('volume_avg'),
                'turnover': data.get('turnover'),
                'timestamp': datetime.now().isoformat(),
                'symbol': data.get('symbol')
            }
            
            self.producer.send(
                'market.volume',
                key=token,
                value=volume_data
            )
            
        except Exception as e:
            logger.error(f"Error publishing volume data: {e}")
    
    async def cache_latest_price(self, token: str, price_data: Dict):
        """Cache latest price in Redis for real-time access"""
        try:
            import redis
            redis_client = redis.StrictRedis(host='redis', port=6379, db=0)
            
            # Store latest price with expiry
            redis_key = f"live_price:{token}"
            redis_client.setex(redis_key, 300, json.dumps(price_data))  # 5 min expiry
            
        except Exception as e:
            logger.error(f"Error caching price data: {e}")
    
    def start_streaming(self, tokens: List[str]):
        """Start streaming for given tokens"""
        try:
            # Initialize components
            if not self.initialize_kafka():
                return False
            
            # Add tokens
            self.add_streaming_tokens(tokens)
            
            # Start WebSocket streaming
            asyncio.create_task(self.start_websocket_streaming())
            
            logger.info(f"Started streaming for {len(tokens)} tokens")
            return True
            
        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            return False
    
    def stop_streaming(self):
        """Stop all streaming"""
        try:
            if self.websocket_connection:
                asyncio.create_task(self.websocket_connection.close())
            
            if self.producer:
                self.producer.close()
            
            self.active_tokens.clear()
            logger.info("Streaming stopped")
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")


# Global instance
market_data_producer = MarketDataProducer()
