from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
from SmartApi import SmartConnect
import pyotp
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from kafka import KafkaProducer
import json
from typing import List
from datetime import datetime
import pandas as pd
from app.config.config import *
import logging
import time

app = FastAPI()

class StreamData(BaseModel):
    correlation_id: str
    mode: int
    messages: dict

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Initialize Kafka producer
def get_kafka_producer():
    return KafkaProducer(
        bootstrap_servers='kafka:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

producer = get_kafka_producer()

def angel_login():
    api_key = API_KEY
    username = USER_NAME
    password = PIN
    totp_token = TOKEN

    obj = SmartConnect(api_key=api_key)

    # Retry mechanism for login
    for _ in range(3):
        try:
            data = obj.generateSession(username, password, pyotp.TOTP(totp_token).now())
            refreshToken = data['data']['refreshToken']
            userProfile = obj.getProfile(refreshToken)
            AUTH_TOKEN = data['data']['jwtToken']
            FEED_TOKEN = obj.getfeedToken()
            print(f'Angel account logged in {obj.rmsLimit()}')

            sws = SmartWebSocketV2(AUTH_TOKEN, api_key, username, FEED_TOKEN)
            sws.connect()
            return obj, sws
        except Exception as e:
            logging.error(f"Login failed: {e}")
            time.sleep(2)

    raise Exception("Failed to login after multiple attempts")

# Callback to handle incoming WebSocket data
async def on_data(wsapp, message, websocket: WebSocket, angel_obj=Depends(angel_login)):
    try:
        correlation_id = "test123"
        mode = 3

        stream_data = StreamData(correlation_id=correlation_id, mode=mode, messages=message)
        stream_data_dict = stream_data.dict()
        stream_data_dict["timestamp"] = datetime.utcnow().isoformat()

        producer.send('websocket-data', value=stream_data_dict)

        await manager.broadcast(json.dumps(stream_data_dict))

    except Exception as e:
        logging.error(f"Error in on_data: {e}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, angel_obj=Depends(angel_login)):
    await manager.connect(websocket)
    try:
        correlation_id = "test123"
        action = 1
        mode = 3
        token_list = [
            {
                "exchangeType": 5,
                "tokens": ["425353","425349"] # Example tokens
            }
        ]
        angel_obj[1].subscribe(correlation_id, mode, token_list)

        while True:
            message = await websocket.receive_text()
            await on_data(websocket, message, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/instrument/")
def get_instruments():
    df = pd.read_csv("app/commodities_instruments.csv")
    symbols = df['name'].unique().tolist()
    return {"symbols": symbols}
