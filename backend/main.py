from fastapi import FastAPI, HTTPException, Query
import redis
import json
import os
from typing import Optional
import pandas as pd

# Local imports
from mcx_symbols import fetch_and_process_commodities, save_tokens_to_csv
from nse_symbols import fetch_and_process_nse
from data_processor import load_all_bhavcopies, compute_daily_analytics

# ✅ FastAPI App
app = FastAPI(title="Stock Analytics API")

# ✅ Redis Config
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


@app.get("/bhavcopy/analytics")
def bhavcopy_analytics(
    segment: str = Query("ALL", description="ALL | FNO | CASH"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    ✅ Load all bhavcopies & return per-date rich analytics (top gainers, losers, delivery, turnover)
    ✅ Filters:
       - segment: ALL, FNO, CASH
       - date range: start_date & end_date
    """
    df = load_all_bhavcopies(segment)
    print(df)
    if df.empty:
        return {"error": "No bhavcopy files found or no data for given segment."}

    # ✅ Filter by date range
    if start_date:
        df = df[df["TRADE_DATE"] >= pd.to_datetime(start_date).date()]
    if end_date:
        df = df[df["TRADE_DATE"] <= pd.to_datetime(end_date).date()]

    if df.empty:
        return {"error": f"No data for segment={segment} in given date range."}

    analytics = compute_daily_analytics(df)
    return {
        "segment": segment,
        "total_days": len(analytics),
        "date_range": [
            str(df["TRADE_DATE"].min()),
            str(df["TRADE_DATE"].max())
        ],
        "analytics": analytics
    }


@app.get("/mcx_tokens")
def get_mcx_tokens():
    df = fetch_and_process_commodities(["CRUDEOIL", "NATURALGAS"])
    csv_path = save_tokens_to_csv(df)
    tokens_list = df[
        ["token", "symbol", "name", "expiry", "strike", "instrumenttype", "call_put"]
    ].to_dict(orient="records")

    return {
        "count": len(tokens_list),
        "saved_csv_path": csv_path,
        "tokens": tokens_list
    }


@app.get("/nse_tokens")
def get_nse_tokens():
    df = fetch_and_process_nse()
    return {"count": len(df), "symbols": df.to_dict(orient="records")}
