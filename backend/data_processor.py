import os
import glob
import pandas as pd
from logzero import logger
from sector.sector_mapping import load_symbol_to_sector  # Custom mapping

# === Constants ===
BHAVCOPY_DIR = "/app/bhavcopy/"
STOCK_INSTRUMENTS_CSV = "/bridge/stocks_instruments.csv"

REQUIRED_COLS = {
    "SYMBOL", "SERIES", "DATE1", "PREV_CLOSE", "OPEN_PRICE", "HIGH_PRICE",
    "LOW_PRICE", "LAST_PRICE", "CLOSE_PRICE", "AVG_PRICE", "TTL_TRD_QNTY",
    "TURNOVER_LACS", "NO_OF_TRADES", "DELIV_QTY", "DELIV_PER"
}


# === Load F&O Symbols from NSE instrument file ===
def load_fno_symbols() -> set:
    if not os.path.exists(STOCK_INSTRUMENTS_CSV):
        logger.warning(f"⚠️ stock_instruments.csv not found at {STOCK_INSTRUMENTS_CSV}")
        return set()

    df = pd.read_csv(STOCK_INSTRUMENTS_CSV)
    if "name" not in df.columns:
        logger.error("❌ 'name' column missing in stock_instruments.csv")
        return set()

    return set(df["name"].astype(str).str.strip().str.upper())


# === MAIN DATA LOADER ===
def load_all_bhavcopies(segment: str = "ALL") -> pd.DataFrame:
    """
    ✅ Loads and enriches bhavcopy data from /app/bhavcopy/
    ✅ Adds:
       - TRADE_DATE
       - SECTOR
       - SEGMENT (FNO/CASH)
    ✅ Filters by segment: ALL | FNO | CASH
    """
    csv_files = sorted(glob.glob(os.path.join(BHAVCOPY_DIR, "*.csv")))
    if not csv_files:
        logger.warning(f"⚠️ No bhavcopy files found in {BHAVCOPY_DIR}")
        return pd.DataFrame()

    all_data = []

    for f in csv_files:
        try:
            df = pd.read_csv(f)
            df.columns = df.columns.str.strip().str.upper()

            # ✅ Keep only required columns
            df = df[list(REQUIRED_COLS & set(df.columns))].copy()

            # ✅ Parse date
            if "DATE1" in df.columns:
                df["DATE1"] = pd.to_datetime(df["DATE1"], errors="coerce")
                df["TRADE_DATE"] = df["DATE1"].dt.date

            # ✅ Numeric conversion
            for col in REQUIRED_COLS:
                if col in ["SYMBOL", "SERIES", "DATE1"]:
                    continue
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # ✅ EQ only
            df["SERIES"] = df["SERIES"].astype(str).str.strip().str.upper()
            df = df[df["SERIES"] == "EQ"]

            all_data.append(df)

        except Exception as e:
            logger.error(f"❌ Error reading {f}: {e}")

    if not all_data:
        return pd.DataFrame()

    merged_df = pd.concat(all_data, ignore_index=True)

    # === Symbol Cleanup ===
    merged_df["SYMBOL"] = merged_df["SYMBOL"].astype(str).str.strip().str.upper()

    # === Add SECTOR ===
    symbol_to_sector = load_symbol_to_sector()
    merged_df["SECTOR"] = merged_df["SYMBOL"].map(symbol_to_sector).fillna("UNKNOWN")

    # === Add SEGMENT ===
    fno_symbols = load_fno_symbols()
    merged_df["SEGMENT"] = merged_df["SYMBOL"].apply(
        lambda sym: "FNO" if sym in fno_symbols else "CASH"
    )

    # === Log unknown symbols in FNO ===
    unknown_fno_symbols = merged_df[
        (merged_df["SECTOR"] == "UNKNOWN") & (merged_df["SEGMENT"] == "FNO")
    ]["SYMBOL"].unique()

    if len(unknown_fno_symbols) > 0:
        logger.warning(
            f"⚠️ UNKNOWN sectors for F&O symbols: {', '.join(sorted(unknown_fno_symbols))}"
        )

    logger.info(f"📊 Loaded {len(merged_df)} EQ rows from {len(csv_files)} CSV files")

    # === Apply Segment Filter (if any) ===
    seg = segment.upper()
    if seg in ["FNO", "CASH"]:
        before = len(merged_df)
        merged_df = merged_df[merged_df["SEGMENT"] == seg]
        logger.info(f"✅ Segment filter '{seg}': {len(merged_df)} rows (from {before})")

    return merged_df


def compute_daily_analytics(df: pd.DataFrame):
    """
    ✅ Generate rich daily analytics for SERIES == 'EQ':
      - Top Gainers / Losers by % change
      - Turnover Leaders
      - Delivery Heavy Stocks
      - Intraday Volatility Spikes
      - Market Breadth (Advancers vs Decliners, Median Delivery%)
      - Sector Average Delivery %
      - Segment stats (FNO/CASH separately)
    """
    analytics_by_date = {}

    if df.empty:
        logger.warning("⚠️ No data available for analytics!")
        return analytics_by_date

    df.columns = df.columns.str.strip().str.upper()
    if "TRADE_DATE" not in df.columns:
        if "DATE1" in df.columns:
            df["TRADE_DATE"] = pd.to_datetime(df["DATE1"], errors="coerce").dt.date
        else:
            logger.error("❌ No DATE1 column found, cannot compute analytics")
            return analytics_by_date

    df = df.dropna(subset=["TRADE_DATE"])
    df["PCT_CHANGE"] = ((df["CLOSE_PRICE"] - df["PREV_CLOSE"]) / df["PREV_CLOSE"]) * 100
    df["INTRADAY_VOL"] = ((df["HIGH_PRICE"] - df["LOW_PRICE"]) / df["OPEN_PRICE"]) * 100
    df["DELIVERY_VALUE"] = df["DELIV_QTY"] * df["AVG_PRICE"]
    df["DELIVERY_RATIO"] = df["DELIV_QTY"] / df["TTL_TRD_QNTY"]

    for trade_date, daily_df in df.groupby("TRADE_DATE"):
        daily_df = daily_df.copy()
        advancers = int((daily_df["PCT_CHANGE"] > 0).sum())
        decliners = int((daily_df["PCT_CHANGE"] < 0).sum())
        median_delivery = round(daily_df["DELIV_PER"].median(), 2)

        top_gainers = daily_df.sort_values("PCT_CHANGE", ascending=False).head(10)[
            ["SYMBOL", "PCT_CHANGE", "CLOSE_PRICE", "TTL_TRD_QNTY", "SECTOR", "SEGMENT"]
        ]
        top_losers = daily_df.sort_values("PCT_CHANGE", ascending=True).head(10)[
            ["SYMBOL", "PCT_CHANGE", "CLOSE_PRICE", "TTL_TRD_QNTY", "SECTOR", "SEGMENT"]
        ]
        high_delivery = daily_df[daily_df["DELIV_PER"] > 70].sort_values(
            "DELIV_PER", ascending=False
        )[
            ["SYMBOL", "DELIV_PER", "DELIV_QTY", "TTL_TRD_QNTY", "SECTOR", "SEGMENT"]
        ]
        turnover_leaders = daily_df.sort_values("TURNOVER_LACS", ascending=False).head(10)[
            ["SYMBOL", "TURNOVER_LACS", "TTL_TRD_QNTY", "SECTOR", "SEGMENT"]
        ]
        high_volatility = daily_df.sort_values("INTRADAY_VOL", ascending=False).head(10)[
            ["SYMBOL", "INTRADAY_VOL", "OPEN_PRICE", "HIGH_PRICE", "LOW_PRICE", "SECTOR", "SEGMENT"]
        ]

        # ✅ Sector-wise average delivery
        sector_delivery = {}
        if "SECTOR" in daily_df.columns:
            sector_stats = daily_df.groupby("SECTOR")["DELIV_PER"].mean().round(2)
            sector_delivery = sector_stats.to_dict()

        # ✅ Segment stats (CASH/FNO)
        segment_stats = {}
        if "SEGMENT" in daily_df.columns:
            segment_groups = daily_df.groupby("SEGMENT")
            for seg, seg_df in segment_groups:
                segment_stats[seg] = {
                    "symbols_count": len(seg_df["SYMBOL"].unique()),
                    "median_delivery": round(seg_df["DELIV_PER"].median(), 2),
                    "top_gainers": seg_df.sort_values("PCT_CHANGE", ascending=False).head(5)[["SYMBOL", "PCT_CHANGE"]].to_dict(orient="records"),
                    "top_losers": seg_df.sort_values("PCT_CHANGE", ascending=True).head(5)[["SYMBOL", "PCT_CHANGE"]].to_dict(orient="records")
                }

        analytics_by_date[str(trade_date)] = {
            "advancers": advancers,
            "decliners": decliners,
            "median_delivery": median_delivery,
            "top_gainers": top_gainers.to_dict(orient="records"),
            "top_losers": top_losers.to_dict(orient="records"),
            "high_delivery": high_delivery.to_dict(orient="records"),
            "turnover_leaders": turnover_leaders.to_dict(orient="records"),
            "volatility_spikes": high_volatility.to_dict(orient="records"),
            "sector_delivery": sector_delivery,
            "segment_stats": segment_stats
        }

    logger.info(f"✅ Generated rich analytics with sector & segment for {len(analytics_by_date)} trade days")
    return analytics_by_date
