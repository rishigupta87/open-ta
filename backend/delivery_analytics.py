from fastapi import APIRouter, Query
from typing import Optional
import pandas as pd
from logzero import logger
from scipy.stats import linregress
from data_processor import load_all_bhavcopies, compute_daily_analytics
import os

router = APIRouter()

# ✅ Load F&O symbols from stock_instruments.csv once
INSTRUMENTS_CSV = "/bridge/stock_instruments.csv"
FNO_SYMBOLS = set()
if os.path.exists(INSTRUMENTS_CSV):
    fno_df = pd.read_csv(INSTRUMENTS_CSV)
    FNO_SYMBOLS = set(fno_df["name"].astype(str).str.upper().str.strip())
    logger.info(f"✅ Loaded {len(FNO_SYMBOLS)} F&O symbols")
else:
    logger.warning("⚠️ stock_instruments.csv not found, F&O segmentation disabled!")

def filter_segment(df: pd.DataFrame, segment: str):
    """Filter bhavcopy df into CASH/FNO/ALL based on stock_instruments.csv"""
    df["SYMBOL"] = df["SYMBOL"].astype(str).str.upper()
    if segment == "FNO":
        return df[df["SYMBOL"].isin(FNO_SYMBOLS)]
    elif segment == "CASH":
        return df[~df["SYMBOL"].isin(FNO_SYMBOLS)]
    return df  # ALL

# @router.get("/analytics/segment_insights")
# def segment_insights(
#     segment: str = Query("ALL", enum=["ALL", "CASH", "FNO"]),
#     top_n: int = 50
# ):
#     """
#     ✅ Combined analytics:
#        - Basic daily analytics (gainers, losers, delivery spikes, turnover)
#        - Increasing delivery% trend (regression slope)
#        - Supports CASH, F&O, ALL segments
#     """
#     df = load_all_bhavcopies()
#     if df.empty:
#         return {"error": "No bhavcopy data"}

#     # ✅ Filter segment
#     df = filter_segment(df, segment)
#     if df.empty:
#         return {"segment": segment, "error": "No symbols found for this segment"}

#     # ✅ Basic Daily Analytics
#     basic_analytics = compute_daily_analytics(df)

#     # ✅ Increasing Delivery% Trend
#     trend_results = []
#     for symbol, sym_df in df.groupby("SYMBOL"):
#         sym_df = sym_df.sort_values("TRADE_DATE")
#         if len(sym_df) < 3:
#             continue

#         x = (pd.to_datetime(sym_df["TRADE_DATE"]) - pd.Timestamp("1970-01-01")).dt.days
#         y = sym_df["DELIV_PER"].fillna(0)
#         slope, _, r_value, _, _ = linregress(x, y)

#         if slope > 0:
#             trend_results.append({
#                 "symbol": symbol,
#                 "start_delivery": float(y.iloc[0]),
#                 "end_delivery": float(y.iloc[-1]),
#                 "trend_slope": round(slope, 4),
#                 "trend_strength": round(r_value ** 2, 3),
#                 "days": len(sym_df)
#             })

#     trend_results = sorted(trend_results, key=lambda x: x["trend_slope"], reverse=True)[:top_n]

#     return {
#         "segment": segment,
#         "symbols_count": df["SYMBOL"].nunique(),
#         "date_range": {
#             "start": str(df["TRADE_DATE"].min()),
#             "end": str(df["TRADE_DATE"].max())
#         },
#         "daily_analytics": basic_analytics,
#         "increasing_delivery": trend_results
#     }
