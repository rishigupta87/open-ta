import streamlit as st
import redis
import json

# Initialize Redis client
redis_client = redis.StrictRedis(host='redis', port=6379, db=0)

# Subscribe to the Redis channel
pubsub = redis_client.pubsub()
pubsub.subscribe('streaming-data-channel')

st.title("Real-Time Stock Market Prices")

# Use a placeholder to dynamically update the data
placeholder = st.empty()

# Continuously listen for new messages on the Redis channel
for message in pubsub.listen():
    if message["type"] == "message":
        data = json.loads(message["data"].decode("utf-8"))
        with placeholder.container():
            st.write(data)
