import threading
import time
import pyotp
from app.config.config import *
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import redis
import json
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException

# Enable debugger
import ptvsd
ptvsd.enable_attach(address=('0.0.0.0', 5678))
print("Debugger is ready to attach. Please connect the debugger.")

# Initialize Redis client
redis_client = redis.StrictRedis(host='redis', port=6379, db=0)

# # Global variables
# streaming_thread = None
# stop_event = threading.Event()
# sws = None  # Global WebSocket instance

def convert_to_ist(utc_timestamp):
    utc_dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
    ist_offset = timedelta(hours=5, minutes=30)
    ist_dt = utc_dt + ist_offset
    return ist_dt.strftime('%Y-%m-%d %H:%M:%S')

class WebSocketStreamer:
    def __init__(self, api_key, username, pin, token):
        self.api_key = api_key
        self.username = username
        self.pin = pin
        self.token = token
        self.sws = None
        self.auth_token = None
        self.feed_token = None
        self.stop_event = threading.Event()

    def login(self):
        obj = SmartConnect(api_key=self.api_key)
        data = obj.generateSession(self.username, self.pin, pyotp.TOTP(self.token).now())
        self.auth_token = data['data']['jwtToken']
        self.feed_token = obj.getfeedToken()

    def on_open(self, wsapp):
        print("WebSocket connection opened")
        correlation_id = "dft_test1"
        mode = 3
        token_list = [{"exchangeType": 5, "tokens": ["430106", "428869", "430268", "429029"]},
                      {"exchangeType": 2, "tokens": ["56547", "37733"]}]
        self.sws.subscribe(correlation_id, mode, token_list)

    def on_data(self, wsapp, message):
        print("Ticks: {}".format(message))
        try:
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
            redis_client.rpush(f"websocket-data:{message['token']}", json.dumps(data_to_store))
        except Exception as e:
            print(f"Error storing data in Redis: {e}")

    def on_error(self, wsapp, error):
        print(f"WebSocket error: {error}")

    def on_close(self, wsapp):
        print("WebSocket connection closed")

    def start_streaming(self):
        try:
            if not self.auth_token:
                self.login()

            self.sws = SmartWebSocketV2(self.auth_token, self.api_key, self.username, self.feed_token)

            # Assign event handlers
            self.sws.on_open = self.on_open
            self.sws.on_data = self.on_data
            self.sws.on_error = self.on_error
            self.sws.on_close = self.on_close

            # Connect to WebSocket
            self.sws.connect()

            # Keep the connection alive
            while not self.stop_event.is_set():
                time.sleep(1)
        except Exception as e:
            print(f"Error during streaming: {e}")
        finally:
            if self.sws:
                self.sws.close_connection()
                self.sws = None

    def stop_streaming(self):
        try:
            if self.sws:
                correlation_id = "dft_test1"
                mode = 3
                token_list = [{"exchangeType": 5, "tokens": ["430106", "428869", "430268", "429029"]},
                              {"exchangeType": 2, "tokens": ["56547", "37733"]}]
                self.sws.unsubscribe(correlation_id, mode, token_list)
                self.sws.close_connection()
                self.sws = None
            self.stop_event.set()
        except Exception as e:
            print(f"Error stopping the WebSocket: {e}")

# FastAPI app instance
app = FastAPI()

# WebSocketStreamer instance
streamer = WebSocketStreamer(API_KEY, USER_NAME, PIN, TOKEN)

# FastAPI endpoint to start streaming
@app.get("/start-streaming/")
def start_streaming_endpoint():
    if streamer.stop_event.is_set():
        raise HTTPException(status_code=400, detail="Streaming already running")
    
    threading.Thread(target=streamer.start_streaming).start()
    return {"status": "Streaming started", "streaming": True}

# FastAPI endpoint to stop streaming
@app.get("/stop-streaming/")
def stop_streaming_endpoint():
    if not streamer.stop_event.is_set():
        streamer.stop_streaming()
        return {"status": "Streaming stopped", "streaming": False}
    
    raise HTTPException(status_code=400, detail="Streaming was not running")

# FastAPI endpoint to check streaming status
@app.get("/streaming-status/")
def streaming_status():
    return {"streaming": not streamer.stop_event.is_set()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0")