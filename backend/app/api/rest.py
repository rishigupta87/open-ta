from fastapi import APIRouter, HTTPException
import threading
import json

from ..streaming.service import streamer, active_streams, redis_client

router = APIRouter()

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