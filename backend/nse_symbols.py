import pandas as pd
import requests
import os
from datetime import datetime

URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

def fetch_nse_data():
    """Fetch NSE JSON data from AngelOne API"""
    response = requests.get(URL)
    response.raise_for_status()
    return response.json()

def preprocess_nse_data(data):
    """Filter NFO data for Futures & Options"""
    df = pd.DataFrame(data)

    # Filter only for NFO Futures & Options
    df = df[
        (df["exch_seg"] == "NFO") &
        (df["instrumenttype"].isin(["FUTSTK", "OPTSTK", "FUTIDX", "OPTIDX"]))
    ]

    # Remove any test symbols
    df = df[~df["name"].str.contains("test", case=False, na=False)]

    # Convert expiry to datetime
    df["expiry"] = pd.to_datetime(df["expiry"], errors="coerce")

    return df

def get_nearest_expiries(group, instrumenttype):
    """Get nearest 2 expiries for Futures, 1 for Options"""
    if "FUT" in instrumenttype:
        nearest_expiries = group["expiry"].nsmallest(2)
    else:
        nearest_expiries = group["expiry"].nsmallest(1)
    return group[group["expiry"].isin(nearest_expiries)]

def process_nse_instruments(filtered_df):
    """Extract strikes, call/put info, keep nearest expiries"""

    # Group and keep only nearest expiries
    filtered_df = filtered_df.groupby(["name", "instrumenttype"]).apply(
        lambda x: get_nearest_expiries(x, x["instrumenttype"].iloc[0])
    ).reset_index(drop=True)

    # Extract call/put info for options
    def extract_call_put(row):
        if row["instrumenttype"] in ["OPTSTK", "OPTIDX"]:
            # Option symbols end with strike+CE/PE, e.g. NIFTY30JAN24500CE
            sym = row["symbol"]
            # Extract strike+CE/PE
            strike_part = "".join(filter(str.isdigit, sym[-8:]))  # last part
            call_put = "CE" if "CE" in sym else "PE" if "PE" in sym else ""
            return pd.Series([float(strike_part) if strike_part else 0.0, call_put])
        else:
            return pd.Series([0.0, ""])

    filtered_df[["strike", "call_put"]] = filtered_df.apply(extract_call_put, axis=1)

    return filtered_df

def save_nse_csvs(df, output_dir):
    """Save separate CSVs for index & stock F&O"""
    index_df = df[df["instrumenttype"].isin(["FUTIDX", "OPTIDX"])]
    stock_df = df[df["instrumenttype"].isin(["FUTSTK", "OPTSTK"])]

    index_path = os.path.join(output_dir, "index_instruments.csv")
    stock_path = os.path.join(output_dir, "stocks_instruments.csv")

    index_df.to_csv(index_path, index=False)
    stock_df.to_csv(stock_path, index=False)

    return index_df, stock_df

def fetch_and_process_nse():
    """Main pipeline: Fetch → Filter → Process → Save"""
    data = fetch_nse_data()
    df = preprocess_nse_data(data)
    df = process_nse_instruments(df)

    # Save into websocket-bridge shared folder
    output_dir = "/websocket-bridge"
    os.makedirs(output_dir, exist_ok=True)

    index_df, stock_df = save_nse_csvs(df, output_dir)

    # Merge both for token list return
    combined = pd.concat([index_df, stock_df])

    return combined[["token", "symbol", "name", "expiry", "strike", "instrumenttype", "call_put"]]
