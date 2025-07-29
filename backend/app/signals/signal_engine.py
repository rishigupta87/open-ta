import json
import asyncio
from kafka import KafkaConsumer
from typing import Dict, List, Optional
import logzero
import os
import redis
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

logger = logzero.logger


class TradingSignalEngine:
    """Real-time trading signal engine using Kafka streams"""
    
    def __init__(self):
        self.kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
        self.redis_client = redis.StrictRedis(host='redis', port=6379, db=0)
        self.price_consumer = None
        self.oi_consumer = None
        self.running = False
        
        # Signal configuration
        self.signal_config = {
            'momentum_threshold': 0.5,  # % price change for momentum signal
            'oi_spike_threshold': 20,   # % OI change for unusual activity
            'volume_spike_multiplier': 2,  # Volume vs average multiplier
            'scalping_range': 0.2,     # % range for scalping signals
        }
        
        # Data buffers for analysis
        self.price_buffer = {}  # Store recent prices for each token
        self.oi_buffer = {}     # Store recent OI data
        self.volume_buffer = {} # Store recent volume data
        
    def initialize_consumers(self):
        """Initialize Kafka consumers"""
        try:
            # Price data consumer
            self.price_consumer = KafkaConsumer(
                'futures.prices',
                'options.prices',
                bootstrap_servers=self.kafka_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='signal_engine_prices',
                auto_offset_reset='latest'
            )
            
            # OI data consumer
            self.oi_consumer = KafkaConsumer(
                'market.oi',
                'market.volume',
                bootstrap_servers=self.kafka_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='signal_engine_oi',
                auto_offset_reset='latest'
            )
            
            logger.info("Kafka consumers initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumers: {e}")
            return False
    
    async def start_signal_processing(self):
        """Start processing market data for signals"""
        if not self.initialize_consumers():
            return
        
        self.running = True
        logger.info("Signal engine started")
        
        # Start processing tasks
        tasks = [
            asyncio.create_task(self.process_price_data()),
            asyncio.create_task(self.process_oi_data()),
            asyncio.create_task(self.cleanup_old_data())
        ]
        
        await asyncio.gather(*tasks)
    
    async def process_price_data(self):
        """Process price data for momentum and scalping signals"""
        while self.running:
            try:
                for message in self.price_consumer:
                    data = message.value
                    token = data['token']
                    
                    # Update price buffer
                    await self.update_price_buffer(token, data)
                    
                    # Generate signals
                    momentum_signal = await self.check_momentum_signal(token, data)
                    scalping_signal = await self.check_scalping_signal(token, data)
                    breakout_signal = await self.check_breakout_signal(token, data)
                    
                    # Publish signals
                    if momentum_signal:
                        await self.publish_signal('momentum', token, momentum_signal)
                    
                    if scalping_signal:
                        await self.publish_signal('scalping', token, scalping_signal)
                    
                    if breakout_signal:
                        await self.publish_signal('breakout', token, breakout_signal)
                
            except Exception as e:
                logger.error(f"Error processing price data: {e}")
                await asyncio.sleep(1)
    
    async def process_oi_data(self):
        """Process OI data for options flow signals"""
        while self.running:
            try:
                for message in self.oi_consumer:
                    data = message.value
                    token = data['token']
                    
                    # Update OI buffer
                    await self.update_oi_buffer(token, data)
                    
                    # Generate OI-based signals
                    oi_spike_signal = await self.check_oi_spike_signal(token, data)
                    unusual_activity_signal = await self.check_unusual_activity(token, data)
                    
                    # Publish signals
                    if oi_spike_signal:
                        await self.publish_signal('oi_spike', token, oi_spike_signal)
                    
                    if unusual_activity_signal:
                        await self.publish_signal('unusual_activity', token, unusual_activity_signal)
                
            except Exception as e:
                logger.error(f"Error processing OI data: {e}")
                await asyncio.sleep(1)
    
    async def update_price_buffer(self, token: str, data: Dict):
        """Update price buffer for technical analysis"""
        try:
            if token not in self.price_buffer:
                self.price_buffer[token] = []
            
            # Keep last 100 price points
            self.price_buffer[token].append({
                'timestamp': data['timestamp'],
                'ltp': data['ltp'],
                'high': data.get('high'),
                'low': data.get('low'),
                'open': data.get('open'),
                'volume': data.get('volume', 0)
            })
            
            # Keep only recent data
            if len(self.price_buffer[token]) > 100:
                self.price_buffer[token] = self.price_buffer[token][-100:]
                
        except Exception as e:
            logger.error(f"Error updating price buffer: {e}")
    
    async def update_oi_buffer(self, token: str, data: Dict):
        """Update OI buffer for options analysis"""
        try:
            if token not in self.oi_buffer:
                self.oi_buffer[token] = []
            
            self.oi_buffer[token].append({
                'timestamp': data['timestamp'],
                'oi': data.get('oi', 0),
                'oi_change': data.get('oi_change', 0),
                'volume': data.get('volume', 0)
            })
            
            # Keep only recent data
            if len(self.oi_buffer[token]) > 50:
                self.oi_buffer[token] = self.oi_buffer[token][-50:]
                
        except Exception as e:
            logger.error(f"Error updating OI buffer: {e}")
    
    async def check_momentum_signal(self, token: str, data: Dict) -> Optional[Dict]:
        """Check for momentum trading signals"""
        try:
            if token not in self.price_buffer or len(self.price_buffer[token]) < 10:
                return None
            
            prices = [p['ltp'] for p in self.price_buffer[token][-10:]]
            current_price = data['ltp']
            
            # Calculate momentum
            price_change = (current_price - prices[0]) / prices[0] * 100
            
            if abs(price_change) > self.signal_config['momentum_threshold']:
                signal_type = 'BUY' if price_change > 0 else 'SELL'
                
                return {
                    'type': signal_type,
                    'strength': min(abs(price_change) / 2, 10),  # Scale 0-10
                    'price': current_price,
                    'change_percent': price_change,
                    'reason': f'Momentum {signal_type.lower()} signal',
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking momentum signal: {e}")
            return None
    
    async def check_scalping_signal(self, token: str, data: Dict) -> Optional[Dict]:
        """Check for scalping signals (mean reversion)"""
        try:
            if token not in self.price_buffer or len(self.price_buffer[token]) < 20:
                return None
            
            prices = [p['ltp'] for p in self.price_buffer[token][-20:]]
            current_price = data['ltp']
            
            # Calculate moving average and standard deviation
            avg_price = np.mean(prices)
            std_dev = np.std(prices)
            
            # Check if price is outside normal range
            upper_bound = avg_price + (std_dev * 1.5)
            lower_bound = avg_price - (std_dev * 1.5)
            
            if current_price > upper_bound:
                return {
                    'type': 'SELL',
                    'strength': 7,
                    'price': current_price,
                    'target': avg_price,
                    'reason': 'Scalping sell - price above upper bound',
                    'timestamp': datetime.now().isoformat()
                }
            elif current_price < lower_bound:
                return {
                    'type': 'BUY',
                    'strength': 7,
                    'price': current_price,
                    'target': avg_price,
                    'reason': 'Scalping buy - price below lower bound',
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking scalping signal: {e}")
            return None
    
    async def check_breakout_signal(self, token: str, data: Dict) -> Optional[Dict]:
        """Check for breakout signals"""
        try:
            if token not in self.price_buffer or len(self.price_buffer[token]) < 30:
                return None
            
            recent_data = self.price_buffer[token][-30:]
            highs = [p['high'] for p in recent_data if p['high']]
            lows = [p['low'] for p in recent_data if p['low']]
            
            if not highs or not lows:
                return None
            
            resistance = max(highs)
            support = min(lows)
            current_price = data['ltp']
            
            # Breakout above resistance
            if current_price > resistance * 1.002:  # 0.2% above resistance
                return {
                    'type': 'BUY',
                    'strength': 9,
                    'price': current_price,
                    'resistance': resistance,
                    'reason': 'Breakout above resistance',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Breakdown below support
            elif current_price < support * 0.998:  # 0.2% below support
                return {
                    'type': 'SELL',
                    'strength': 9,
                    'price': current_price,
                    'support': support,
                    'reason': 'Breakdown below support',
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking breakout signal: {e}")
            return None
    
    async def check_oi_spike_signal(self, token: str, data: Dict) -> Optional[Dict]:
        """Check for unusual OI activity"""
        try:
            oi_change = data.get('oi_change', 0)
            
            if abs(oi_change) > self.signal_config['oi_spike_threshold']:
                signal_type = 'BULLISH' if oi_change > 0 else 'BEARISH'
                
                return {
                    'type': signal_type,
                    'strength': min(abs(oi_change) / 5, 10),
                    'oi_change': oi_change,
                    'reason': f'OI spike - {signal_type.lower()} sentiment',
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking OI spike signal: {e}")
            return None
    
    async def check_unusual_activity(self, token: str, data: Dict) -> Optional[Dict]:
        """Check for unusual trading activity"""
        try:
            if token not in self.oi_buffer or len(self.oi_buffer[token]) < 10:
                return None
            
            recent_volumes = [p['volume'] for p in self.oi_buffer[token][-10:]]
            avg_volume = np.mean(recent_volumes) if recent_volumes else 0
            current_volume = data.get('volume', 0)
            
            if current_volume > avg_volume * self.signal_config['volume_spike_multiplier']:
                return {
                    'type': 'VOLUME_SPIKE',
                    'strength': 8,
                    'volume': current_volume,
                    'avg_volume': avg_volume,
                    'multiplier': current_volume / avg_volume if avg_volume > 0 else 0,
                    'reason': 'Unusual volume activity detected',
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking unusual activity: {e}")
            return None
    
    async def publish_signal(self, signal_type: str, token: str, signal_data: Dict):
        """Publish trading signal to Redis and potentially Kafka"""
        try:
            signal = {
                'signal_type': signal_type,
                'token': token,
                'signal_id': f"{token}_{signal_type}_{int(datetime.now().timestamp())}",
                **signal_data
            }
            
            # Store in Redis with expiry
            redis_key = f"trading_signal:{token}:{signal_type}"
            self.redis_client.setex(redis_key, 300, json.dumps(signal))  # 5 min expiry
            
            # Also store in recent signals list
            recent_signals_key = "recent_trading_signals"
            self.redis_client.lpush(recent_signals_key, json.dumps(signal))
            self.redis_client.ltrim(recent_signals_key, 0, 99)  # Keep last 100 signals
            
            logger.info(f"Published {signal_type} signal for token {token}: {signal_data['type']}")
            
        except Exception as e:
            logger.error(f"Error publishing signal: {e}")
    
    async def cleanup_old_data(self):
        """Periodic cleanup of old data"""
        while self.running:
            try:
                # Clean up old buffer data
                cutoff_time = datetime.now() - timedelta(hours=1)
                
                for token in list(self.price_buffer.keys()):
                    self.price_buffer[token] = [
                        p for p in self.price_buffer[token]
                        if datetime.fromisoformat(p['timestamp']) > cutoff_time
                    ]
                
                for token in list(self.oi_buffer.keys()):
                    self.oi_buffer[token] = [
                        p for p in self.oi_buffer[token]
                        if datetime.fromisoformat(p['timestamp']) > cutoff_time
                    ]
                
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                await asyncio.sleep(60)
    
    def stop(self):
        """Stop the signal engine"""
        self.running = False
        if self.price_consumer:
            self.price_consumer.close()
        if self.oi_consumer:
            self.oi_consumer.close()
        logger.info("Signal engine stopped")


# Global instance
signal_engine = TradingSignalEngine()
