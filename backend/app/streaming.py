import threading
import time
import pyotp
import redis
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException

from app.config.config import *
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

# Enable debugger
import ptvsd
ptvsd.enable_attach(address=('0.0.0.0', 5678))
print("Debugger is ready to attach. Please connect the debugger.")

# Initialize Redis client
redis_client = redis.StrictRedis(host='redis', port=6379, db=0)

# Dictionary to hold the active streaming threads
active_streams = {}

# Create a FastAPI router
router = APIRouter()

def convert_to_ist(utc_timestamp):
    utc_dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
    ist_offset = timedelta(hours=5, minutes=30)
    ist_dt = utc_dt + ist_offset
    return ist_dt.strftime('%Y-%m-%d %H:%M:%S')

def load_futures_tokens(file_path, exchange_type):
    """Load FUTURES tokens from a CSV file and map them to their corresponding name and expiry."""
    try:
        df = pd.read_csv(file_path)
        df['token'] = df['token'].astype(str)  # Ensure tokens are strings
        futures_tokens = df[(df['instrumenttype'].str.startswith('FUT')) & (df['exch_seg'] == exchange_type)]

        print(f"Tokens loaded from {file_path}: {futures_tokens['token'].tolist()}")

        # Create a dictionary mapping each token to its name and expiry
        token_map = {row['token']: {'name': row['name'], 'expiry': row['expiry']} for _, row in futures_tokens.iterrows()}
        print(f"Token map: {token_map}")
        token_list = futures_tokens['token'].tolist()

        return token_list, token_map
    except Exception as e:
        print(f"Error loading futures tokens from {file_path}: {e}")
        return [], {}

class WebSocketStreamer:
    def __init__(self, api_key, username, pin, token):
        self.api_key = api_key
        self.username = username
        self.pin = pin
        self.token = token
        self.sws = None
        self.auth_token = None
        self.feed_token = None
        self.active_categories = {}  # To keep track of active categories and their tokens
        self.token_maps = {}  # To store token maps for each category

    def login(self):
        obj = SmartConnect(api_key=self.api_key)
        data = obj.generateSession(self.username, self.pin, pyotp.TOTP(self.token).now())
        self.auth_token = data['data']['jwtToken']
        self.feed_token = obj.getfeedToken()

    def on_open(self, wsapp):
        print("WebSocket connection opened")
        for category, token_list in self.active_categories.items():
            correlation_id = f"{category}_id"
            mode = 3
            self.sws.subscribe(correlation_id, mode, token_list)

    def on_data(self, wsapp, message):
        print(f"Ticks:{message}")
        try:
            token = str(message['token'])
            name_expiry = None

            # Search for the token in the token_maps
            for token_map in self.token_maps.values():
                if token in token_map:
                    name_expiry = token_map[token]
                    break

            if not name_expiry:
                print(f"Token {token} not found in any category.")
                return

            name = name_expiry['name']
            expiry = name_expiry['expiry']

            data_to_store = {
                "exchange_timestamp": convert_to_ist(message["exchange_timestamp"] / 1000),
                "last_traded_price": message["last_traded_price"] / 100,
                "last_traded_quantity": message["last_traded_quantity"],
                "average_traded_price": message["average_traded_price"] / 100,
                "volume_trade_for_the_day": message["volume_trade_for_the_day"],
                "total_buy_quantity": message["total_buy_quantity"],
                "total_sell_quantity": message["total_sell_quantity"],
                "open_price_of_the_day": message["open_price_of_the_day"] / 100,
                "high_price_of_the_day": message["high_price_of_the_day"] / 100,
                "low_price_of_the_day": message["low_price_of_the_day"] / 100,
                "closed_price": message["closed_price"] / 100,
                "last_traded_timestamp": convert_to_ist(message["last_traded_timestamp"]),
                "open_interest": message["open_interest"],
                "open_interest_change_percentage": message["open_interest_change_percentage"]
            }

            redis_key = f"websocket-data:{name}:{token}:{expiry}"

            # Store the new data
            redis_client.rpush(redis_key, json.dumps(data_to_store))
            redis_client.publish('streaming-data-channel', json.dumps(data_to_store))
            
        except Exception as e:
            print(f"Error storing data in Redis: {e}")

    def on_error(self, wsapp, error):
        print(f"WebSocket error: {error}")

    def on_close(self, wsapp):
        print("WebSocket connection closed")

    def start_streaming(self, category):
        try:
            if category in self.active_categories:
                print(f"Streaming already running for {category}")
                return
            
            if not self.auth_token:
                self.login()

            if category == "Index":
                tokens, token_map = load_futures_tokens('/app/tokens/index_instruments.csv', "NFO")
                exchange_type = 2  # NSE
            elif category == "Stocks":
                tokens, token_map = load_futures_tokens('/app/tokens/stocks_instruments.csv', "NFO")
                exchange_type = 2  # NSE
            elif category == "Commodities":
                tokens, token_map = load_futures_tokens('/app/tokens/commodities_instruments.csv', "MCX")
                exchange_type = 5  # MCX
            else:
                raise HTTPException(status_code=400, detail="Invalid category")

            if not tokens:
                raise HTTPException(status_code=404, detail="No FUTURES tokens found")

            # Prepare the token list
            token_list = [{"exchangeType": exchange_type, "tokens": tokens}]
            self.active_categories[category] = token_list
            self.token_maps[category] = token_map  # Store the token_map in the class

            # Start WebSocket connection if it's not already open
            if not self.sws:
                self.sws = SmartWebSocketV2(self.auth_token, self.api_key, self.username, self.feed_token)
                self.sws.on_open = self.on_open
                self.sws.on_data = self.on_data
                self.sws.on_error = self.on_error
                self.sws.on_close = self.on_close
                threading.Thread(target=self.sws.connect).start()  # Start WebSocket connection in a separate thread
                print(f"Started WebSocket connection for {category}")
            else:
                self.sws.subscribe(f"{category}_id", 3, token_list)
        
        except Exception as e:
            print(f"Error during streaming for {category}: {e}")

    def stop_streaming(self, category):
        try:
            if category in self.active_categories:
                correlation_id = f"{category}_id"
                mode = 3
                token_list = self.active_categories.pop(category)
                self.sws.unsubscribe(correlation_id, mode, token_list)
                print(f"Stopped streaming for {category}")

            if not self.active_categories:
                if self.sws:
                    self.sws.close_connection()
                    self.sws = None
                    print("No active streams, WebSocket connection closed.")

        except Exception as e:
            print(f"Error stopping the WebSocket for {category}: {e}")

# WebSocketStreamer instance
streamer = WebSocketStreamer(API_KEY, USER_NAME, PIN, TOKEN)

# FastAPI endpoints
@router.get("/start-streaming/")
async def start_streaming_endpoint(category: str):
    if category in active_streams:
        raise HTTPException(status_code=400, detail=f"Streaming already running for {category}")
    
    stream_thread = threading.Thread(target=streamer.start_streaming, args=(category,))
    stream_thread.start()
    active_streams[category] = stream_thread
    return {"status": f"Streaming started for {category}", "streaming": True}

@router.get("/stop-streaming/")
async def stop_streaming_endpoint(category: str):
    if category not in active_streams:
        raise HTTPException(status_code=400, detail=f"Streaming not running for {category}")
    
    streamer.stop_streaming(category)
    active_streams[category].join()
    del active_streams[category]
    return {"status": f"Streaming stopped for {category}", "streaming": False}

@router.get("/redis-data/")
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

@router.delete("/redis-flush/")
async def delete_all_redis_data():
    try:
        redis_client.flushdb()
        return {"status": "Data deleted successfully."}
    except Exception as e:
        print(f"Error deleting data from Redis: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.get("/running-streams/")
async def get_running_streams():
    """
    Endpoint to return all currently running streams.
    """
    running_streams = list(streamer.active_categories.keys())
    
    if not running_streams:
        return {"message": "No streams are currently running."}

    return {"running_streams": running_streams}
