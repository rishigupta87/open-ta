import strawberry
import threading
import json
from typing import List, Optional
from fastapi import HTTPException

from ..streaming.service import streamer, active_streams, redis_client
from ..streaming.models import StreamingStatus, TokenInfo, MarketData, RedisData

# Define GraphQL queries
@strawberry.type
class Query:
    @strawberry.field
    def running_streams(self) -> List[str]:
        """Get all currently running streams."""
        return list(streamer.active_categories.keys())
    
    @strawberry.field
    def token_info(self, category: str) -> List[TokenInfo]:
        """Get token information for a specific category."""
        if category not in streamer.token_maps:
            return []
        
        token_map = streamer.token_maps[category]
        result = []
        
        for token, info in token_map.items():
            result.append(TokenInfo(
                name=info['name'],
                token=token,
                expiry=info['expiry']
            ))
        
        return result
    
    @strawberry.field
    def redis_data(self) -> List[RedisData]:
        """Fetch and return all data from Redis for all tokens."""
        try:
            keys = redis_client.keys("websocket-data:*")
            result = []
            
            for key in keys:
                key_str = key.decode("utf-8")
                data = redis_client.lrange(key, 0, -1)
                parsed_data = []
                
                for item in data:
                    item_dict = json.loads(item.decode("utf-8"))
                    parsed_data.append(MarketData(**item_dict))
                
                result.append(RedisData(key=key_str, data=parsed_data))
            
            return result
        except Exception as e:
            print(f"Error fetching data from Redis: {e}")
            return []

# Define GraphQL mutations
@strawberry.type
class Mutation:
    @strawberry.mutation
    def start_streaming(self, category: str) -> StreamingStatus:
        """Start streaming for a category"""
        try:
            if category in active_streams:
                return StreamingStatus(
                    category=category,
                    streaming=True,
                    status=f"Streaming already running for {category}"
                )
            
            stream_thread = threading.Thread(target=streamer.start_streaming, args=(category,))
            stream_thread.start()
            active_streams[category] = stream_thread
            
            return StreamingStatus(
                category=category,
                streaming=True,
                status=f"Streaming started for {category}"
            )
        except Exception as e:
            return StreamingStatus(
                category=category,
                streaming=False,
                status=f"Error starting streaming: {str(e)}"
            )
    
    @strawberry.mutation
    def stop_streaming(self, category: str) -> StreamingStatus:
        """Stop streaming for a category"""
        try:
            if category not in active_streams:
                return StreamingStatus(
                    category=category,
                    streaming=False,
                    status=f"No streaming for {category}"
                )
            
            streamer.stop_streaming(category)
            active_streams[category].join()
            del active_streams[category]
            
            return StreamingStatus(
                category=category,
                streaming=False,
                status=f"Streaming stopped for {category}"
            )
        except Exception as e:
            return StreamingStatus(
                category=category,
                streaming=False,
                status=f"Error stopping streaming: {str(e)}"
            )
    
    @strawberry.mutation
    def flush_redis(self) -> bool:
        """Delete all data from Redis."""
        try:
            redis_client.flushdb()
            return True
        except Exception as e:
            print(f"Error deleting data from Redis: {e}")
            return False