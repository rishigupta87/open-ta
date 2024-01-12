# main.py

from fastapi import FastAPI, HTTPException, WebSocket, Depends
from pydantic import BaseModel
import aioredis
from SmartApi import SmartConnect
import pyotp
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from logzero import logger
import pandas as pd
import requests
from datetime import datetime, date, time, timedelta
import config
import math



app = FastAPI()


# Initialize an asynchronous Redis connection
redis = aioredis.from_url("redis://localhost:6379/0")


class StreamData(BaseModel):
    correlation_id: str
    mode: int
    messages: dict



def angel_login():
    api_key = config.API_KEY
    username = config.USER_NAME
    password = config.PIN
    totp_token = config.TOKEN

    obj = SmartConnect(api_key=api_key)
    data = obj.generateSession(username, password, pyotp.TOTP(totp_token).now())
    refreshToken = data['data']['refreshToken']
    userProfile = obj.getProfile(refreshToken)
    AUTH_TOKEN = data['data']['jwtToken']
    FEED_TOKEN = obj.getfeedToken()
    print(f'Angel account logged in {obj.rmsLimit()}')

    # Create the SmartWebSocketV2 object
    sws = SmartWebSocketV2(AUTH_TOKEN, api_key, username, FEED_TOKEN)

    return obj, sws

# Callback to handle incoming WebSocket data
async def on_data(wsapp, message, angel_obj=Depends(angel_login)):
    try:
        correlation_id = "test123"  # Replace with your correlation_id logic
        mode = 3  # Replace with your mode logic

        stream_data = StreamData(correlation_id=correlation_id, mode=mode, messages=message)
        
        # Convert stream_data to a dictionary
        stream_data_dict = stream_data.model_dump()

        # Add timestamp to the data
        stream_data_dict["timestamp"] = datetime.utcnow().isoformat()

        # Add the data to the Redis stream
        redis_key = f"websocket_data:{correlation_id}:{mode}"
        await redis.xadd(redis_key, stream_data_dict)

        # Perform other processing if needed
        # ...

    except Exception as e:
        print(e)

# WebSocket endpoint using the on_data callback and the angel_login dependency
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, angel_obj=Depends(angel_login)):
    await websocket.accept()

    # Your existing logic for handling WebSocket connection
    some_error_condition = False
    if some_error_condition:
        error_message = "Simulated error"
        if hasattr(angel_obj.sws, 'on_error'):
            angel_obj[1].on_error("Custom Error Type", error_message)
    else:
        correlation_id = "test123"
        action = 1
        mode = 3
        token_list = [
            {
                "exchangeType": 5,
                "tokens": ["425353","425349"] # 6200 PE, CE
            }
        ]
        angel_obj[1].subscribe(correlation_id, mode, token_list)

    # Loop to handle incoming WebSocket messages
    while True:
        message = await websocket.receive_text()
        await on_data(websocket, message)