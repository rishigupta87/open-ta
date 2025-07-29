import asyncio
import json
import redis
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket
import logzero

logger = logzero.logger


class RealTimeDataManager:
    """Manager for real-time market data streaming"""
    
    def __init__(self):
        self.subscribers: Dict[str, Set[WebSocket]] = {}
        self.latest_data: Dict[str, Dict[str, Any]] = {}
        self.redis_client = redis.StrictRedis(host='redis', port=6379, db=0)
    
    def subscribe(self, symbol: str, websocket: WebSocket):
        """Subscribe a WebSocket to real-time data for a symbol"""
        if symbol not in self.subscribers:
            self.subscribers[symbol] = set()
        
        self.subscribers[symbol].add(websocket)
        logger.info(f"WebSocket subscribed to {symbol}")
        
        # Send latest data if available
        if symbol in self.latest_data:
            asyncio.create_task(self._send_to_websocket(
                websocket, 
                symbol, 
                self.latest_data[symbol]
            ))
    
    def unsubscribe(self, symbol: str, websocket: WebSocket):
        """Unsubscribe a WebSocket from real-time data for a symbol"""
        if symbol in self.subscribers:
            self.subscribers[symbol].discard(websocket)
            if not self.subscribers[symbol]:
                del self.subscribers[symbol]
            logger.info(f"WebSocket unsubscribed from {symbol}")
    
    def update_data(self, symbol: str, data: Dict[str, Any]):
        """Update real-time data for a symbol and broadcast to subscribers"""
        self.latest_data[symbol] = data
        
        # Store in Redis
        redis_key = f"market-data:{symbol}"
        self.redis_client.setex(redis_key, 300, json.dumps(data))  # 5 minute expiry
        
        # Broadcast to subscribers
        if symbol in self.subscribers:
            for websocket in self.subscribers[symbol].copy():
                asyncio.create_task(self._send_to_websocket(websocket, symbol, data))
    
    async def _send_to_websocket(self, websocket: WebSocket, symbol: str, data: Dict[str, Any]):
        """Send data to a specific WebSocket"""
        try:
            message = {
                "type": "market_data",
                "symbol": symbol,
                "data": data,
                "timestamp": data.get("timestamp", "")
            }
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Failed to send data to WebSocket for {symbol}: {e}")
            # Remove failed WebSocket from subscribers
            if symbol in self.subscribers:
                self.subscribers[symbol].discard(websocket)
    
    def get_latest_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the latest data for a symbol"""
        # Try to get from memory first
        if symbol in self.latest_data:
            return self.latest_data[symbol]
        
        # Try to get from Redis
        try:
            redis_key = f"market-data:{symbol}"
            data = self.redis_client.get(redis_key)
            if data:
                return json.loads(data.decode('utf-8'))
        except Exception as e:
            logger.error(f"Error retrieving data from Redis for {symbol}: {e}")
        
        return None
    
    def get_all_symbols(self) -> Set[str]:
        """Get all symbols with active data"""
        return set(self.latest_data.keys())
    
    def cleanup(self):
        """Clean up resources"""
        self.subscribers.clear()
        self.latest_data.clear()
        logger.info("RealTimeDataManager cleanup completed")


# Global instance
realtime_data_manager = RealTimeDataManager()
