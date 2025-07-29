import threading
import time
import json
import redis
from datetime import datetime
from typing import Dict, Any
import logzero

logger = logzero.logger


class WebSocketStreamer:
    """Service for managing WebSocket data streaming"""
    
    def __init__(self):
        self.active_categories: Dict[str, Dict[str, Any]] = {}
        self.redis_client = redis.StrictRedis(host='redis', port=6379, db=0)
        self._stop_events: Dict[str, threading.Event] = {}
    
    def start_streaming(self, category: str):
        """Start streaming for a given category"""
        if category in self.active_categories:
            logger.warning(f"Streaming already active for category: {category}")
            return
        
        logger.info(f"Starting streaming for category: {category}")
        
        # Create stop event for this category
        stop_event = threading.Event()
        self._stop_events[category] = stop_event
        
        # Initialize category info
        self.active_categories[category] = {
            'started_at': datetime.now(),
            'message_count': 0,
            'status': 'active'
        }
        
        # Start the streaming loop
        self._streaming_loop(category, stop_event)
    
    def stop_streaming(self, category: str):
        """Stop streaming for a given category"""
        if category not in self.active_categories:
            logger.warning(f"No active streaming for category: {category}")
            return
        
        logger.info(f"Stopping streaming for category: {category}")
        
        # Signal the streaming loop to stop
        if category in self._stop_events:
            self._stop_events[category].set()
        
        # Clean up category info
        if category in self.active_categories:
            del self.active_categories[category]
        
        if category in self._stop_events:
            del self._stop_events[category]
    
    def _streaming_loop(self, category: str, stop_event: threading.Event):
        """Main streaming loop for a category"""
        message_count = 0
        
        while not stop_event.is_set():
            try:
                # Generate sample data (replace with actual data source)
                sample_data = {
                    'category': category,
                    'timestamp': datetime.now().isoformat(),
                    'data': {
                        'value': message_count,
                        'status': 'active'
                    }
                }
                
                # Publish to Redis
                redis_key = f"websocket-data:{category}:stream:{int(time.time())}"
                self.redis_client.lpush(redis_key, json.dumps(sample_data))
                self.redis_client.expire(redis_key, 3600)  # Expire after 1 hour
                
                # Update message count
                message_count += 1
                if category in self.active_categories:
                    self.active_categories[category]['message_count'] = message_count
                
                # Publish to streaming channel
                self.redis_client.publish('streaming-data-channel', json.dumps(sample_data))
                
                logger.debug(f"Published message {message_count} for category {category}")
                
                # Wait before next iteration
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in streaming loop for {category}: {e}")
                time.sleep(5)  # Wait before retrying
    
    def get_active_categories(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all active streaming categories"""
        return self.active_categories.copy()
    
    def is_streaming(self, category: str) -> bool:
        """Check if streaming is active for a category"""
        return category in self.active_categories


# Global streamer instance
streamer = WebSocketStreamer()

# For backward compatibility
active_streams = {}
