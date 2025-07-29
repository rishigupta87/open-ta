from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import strawberry
from strawberry.fastapi import GraphQLRouter
import json
import redis
import threading
from typing import List
from datetime import datetime
import logzero
logger = logzero.logger
from app.websocket_handler import websocket_manager
from trading.realtime_data_manager import realtime_data_manager
from trading.smart_api_manager import SmartAPIManager
from trading.models import TradingSymbol

# Create FastAPI app
app = FastAPI(title="Algo Trading API")

# Initialize Redis client
redis_client = redis.StrictRedis(host='redis', port=6379, db=0)

# Dictionary to hold the active streaming threads
active_streams = {}
smart_api_manager = None

# Import the WebSocketStreamer class from the correct location
from app.streaming.service import WebSocketStreamer, streamer, active_streams

@strawberry.type
class TradingStatus:
    strategy_name: str
    is_active: bool
    pnl: float
    positions: str
    total_trades: int

@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello from Algo Trading API!"
    
    @strawberry.field
    def running_streams(self) -> List[str]:
        return list(active_streams.keys())
    
    @strawberry.field
    def trading_status(self) -> List[TradingStatus]:
        return []

@strawberry.type
class Mutation:
    @strawberry.mutation
    def start_streaming(self, category: str) -> str:
        if category in active_streams:
            return f"Streaming already running for {category}"
        
        # Your existing streaming logic
        stream_thread = threading.Thread(target=start_data_stream, args=(category,))
        stream_thread.start()
        active_streams[category] = stream_thread
        return f"Streaming started for {category}"
    
    @strawberry.mutation
    def stop_streaming(self, category: str) -> str:
        if category not in active_streams:
            return f"No streaming for {category}"
        
        active_streams[category].join()
        del active_streams[category]
        return f"Streaming stopped for {category}"
    
    @strawberry.mutation
    def initialize_trading(self, api_key: str, username: str, pwd: str, totp_token: str) -> str:
        global smart_api_manager
        
        try:
            smart_api_manager = SmartAPIManager(api_key, username, pwd, totp_token)
            if smart_api_manager.authenticate():
                return "Trading initialized successfully"
            else:
                return "Authentication failed"
        except Exception as e:
            return f"Initialization failed: {str(e)}"
    
    @strawberry.mutation
    def start_strategy(self, strategy_name: str, symbols: str, capital: float = 100000) -> str:
        return "Strategy functionality not implemented yet"
    
    @strawberry.mutation
    def stop_strategy(self, strategy_name: str) -> str:
        return "Strategy functionality not implemented yet"

def start_data_stream(category: str):
    # Your existing streaming logic here
    pass

# Create the GraphQL schema and router
schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the GraphQL router - IMPORTANT: no prefix here
app.include_router(graphql_app, prefix="/graphql")

@app.websocket("/ws/market-data/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await websocket_manager.connect(websocket, symbol)
    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif message.get("type") == "subscribe":
                new_symbol = message.get("symbol")
                if new_symbol:
                    realtime_data_manager.subscribe(new_symbol, websocket)
            
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, symbol)

@app.get("/api/market-data/{symbol}")
async def get_market_data(symbol: str):
    """REST endpoint to get latest market data"""
    data = realtime_data_manager.get_latest_data(symbol)
    return {"symbol": symbol, "data": data}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Initialize trading components
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Algo Trading API...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Algo Trading API...")
    # Cleanup connections
    if smart_api_manager:
        smart_api_manager.disconnect()

# Define REST endpoints
@app.get("/start-streaming/")
async def start_streaming_endpoint(category: str):
    if category in active_streams:
        raise HTTPException(status_code=400, detail=f"Streaming already running for {category}")
    
    stream_thread = threading.Thread(target=streamer.start_streaming, args=(category,))
    stream_thread.start()
    active_streams[category] = stream_thread
    return {"status": f"Streaming started for {category}", "streaming": True}

@app.get("/stop-streaming/")
async def stop_streaming_endpoint(category: str):
    if category not in active_streams:
        raise HTTPException(status_code=400, detail=f"Streaming not running for {category}")
    
    streamer.stop_streaming(category)
    active_streams[category].join()
    del active_streams[category]
    return {"status": f"Streaming stopped for {category}", "streaming": False}

@app.get("/redis-data/")
async def get_all_redis_data():
    """
    Fetch and return all data from Redis for all tokens.
    """
    try:
        keys = redis_client.keys("websocket-data:*")
        all_data = {}
        
        for key in keys:
            key_parts = key.decode("utf-8").split(":")
            name = key_parts[1]
            token = key_parts[2]
            expiry = key_parts[3]
            
            data = redis_client.lrange(key, 0, -1)
            parsed_data = [json.loads(item.decode("utf-8")) for item in data]

            # Use a combination of name, token, and expiry as a composite key
            composite_key = f"{name}-{token}-{expiry}"
            all_data[composite_key] = parsed_data

        if not all_data:
            return {"message": "No data available in Redis"}

        return {"data": all_data}
    except Exception as e:
        print(f"Error fetching data from Redis: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.delete("/redis-flush/")
async def delete_all_redis_data():
    try:
        redis_client.flushdb()
        return {"status": "Data deleted successfully."}
    except Exception as e:
        print(f"Error deleting data from Redis: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@app.get("/running-streams/")
async def get_running_streams():
    """
    Endpoint to return all currently running streams.
    """
    running_streams = list(streamer.active_categories.keys())
    
    if not running_streams:
        return {"message": "No streams are currently running."}

    return {"running_streams": running_streams}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
