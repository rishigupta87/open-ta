from fastapi import FastAPI
from app.streaming import start_streaming_endpoint, stop_streaming_endpoint, get_all_redis_data, delete_all_redis_data, get_running_streams

app = FastAPI()

# Include streaming endpoints
app.add_api_route("/start-streaming/", start_streaming_endpoint)
app.add_api_route("/stop-streaming/", stop_streaming_endpoint)
app.add_api_route("/redis-data/", get_all_redis_data)
app.add_api_route("/redis-flush/", delete_all_redis_data)
app.add_api_route("/running-streams/", get_running_streams)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Stock Market Streaming App"}

# Additional routes or logic can be added her

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
