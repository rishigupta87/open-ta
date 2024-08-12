from fastapi import FastAPI
from app.streaming import router as streaming_router

app = FastAPI()

# Include streaming router
app.include_router(streaming_router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Stock Market Streaming App"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
