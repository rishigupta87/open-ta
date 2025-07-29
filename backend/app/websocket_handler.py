from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
from trading.realtime_data_manager import realtime_data_manager
from logzero import logger

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        
        if symbol not in self.active_connections:
            self.active_connections[symbol] = set()
        
        self.active_connections[symbol].add(websocket)
        
        # Subscribe to real-time data
        realtime_data_manager.subscribe(symbol, websocket)
        
        logger.info(f"WebSocket connected for symbol: {symbol}")
    
    def disconnect(self, websocket: WebSocket, symbol: str):
        if symbol in self.active_connections:
            self.active_connections[symbol].discard(websocket)
            if not self.active_connections[symbol]:
                del self.active_connections[symbol]
        
        # Unsubscribe from real-time data
        realtime_data_manager.unsubscribe(symbol, websocket)
        
        logger.info(f"WebSocket disconnected for symbol: {symbol}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast_to_symbol(self, message: str, symbol: str):
        if symbol in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[symbol].copy():
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.warning(f"Failed to send message: {e}")
                    disconnected.add(connection)
            
            # Clean up disconnected connections
            self.active_connections[symbol] -= disconnected

websocket_manager = WebSocketManager()