from fastapi import FastAPI
from app.streaming import start_streaming_endpoint, stop_streaming_endpoint

app = FastAPI()

# Include streaming endpoints
app.add_api_route("/start-streaming/", start_streaming_endpoint)
app.add_api_route("/stop-streaming/", stop_streaming_endpoint)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Stock Market Streaming App"}

# Additional routes or logic can be added here

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
