import os
import glob
import pandas as pd

BHAVCOPY_DIR = "/app/bhavcopy/"

def load_all_bhavcopies():
    """
    Load ALL bhavcopy CSVs in folder into single DataFrame.
    Adds DATE column extracted from filename.
    """
    files = sorted(glob.glob(os.path.join(BHAVCOPY_DIR, "sec_*.csv")))
    if not files:
        raise FileNotFoundError("❌ No bhavcopy files found")

    dfs = []
    for f in files:
        # Extract date from filename sec_DDMMYYYY.csv
        date_str = os.path.basename(f).replace("sec_", "").replace(".csv", "")
        trade_date = pd.to_datetime(date_str, format="%d%m%Y", errors="coerce")

        df = pd.read_csv(f)
        df.columns = [c.strip().upper() for c in df.columns]

        # Ensure columns exist
        required_cols = {"SYMBOL","SERIES","DATE1","PREV_CLOSE","OPEN_PRICE","HIGH_PRICE","LOW_PRICE","LAST_PRICE","CLOSE_PRICE","AVG_PRICE","TTL_TRD_QNTY","TURNOVER_LACS","NO_OF_TRADES","DELIV_QTY","DELIV_PER"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"❌ Missing columns in {f}: {missing}")

        df["DATE1"] = trade_date
        dfs.append(df)

    all_df = pd.concat(dfs, ignore_index=True)
    all_df.sort_values(["SYMBOL", "DATE1"], inplace=True)
    return all_df


def compute_daily_metrics(df):
    """
    For EACH date:
      - Top gainers/losers
      - Volume spike vs 5-day avg
      - Turnover leaders
    """
    results = {}

    for trade_date, day_df in df.groupby("DATE1"):
        day_name = trade_date.strftime("%Y-%m-%d")

        # ✅ % Change vs PREVCLOSE
        day_df["PCT_CHANGE"] = ((day_df["CLOSE"] - day_df["PREVCLOSE"]) / day_df["PREVCLOSE"]) * 100

        top_gainers = (
            day_df.sort_values("PCT_CHANGE", ascending=False)
            .head(10)[["SYMBOL", "CLOSE", "PCT_CHANGE", "TOTTRDQTY", "TOTTRDVAL"]]
            .to_dict(orient="records")
        )
        top_losers = (
            day_df.sort_values("PCT_CHANGE", ascending=True)
            .head(10)[["SYMBOL", "CLOSE", "PCT_CHANGE", "TOTTRDQTY", "TOTTRDVAL"]]
            .to_dict(orient="records")
        )

        # ✅ Volume spike vs rolling avg (last 5 days)
        symbol_volumes = df[df["SYMBOL"].isin(day_df["SYMBOL"])]
        vol_5d_avg = (
            symbol_volumes.groupby("SYMBOL")["TOTTRDQTY"]
            .rolling(5, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )
        symbol_volumes = symbol_volumes.assign(VOL_5D_AVG=vol_5d_avg)

        merged_today = pd.merge(
            day_df,
            symbol_volumes[symbol_volumes["DATE1"] == trade_date][["SYMBOL", "VOL_5D_AVG"]],
            on="SYMBOL",
            how="left"
        )
        merged_today["VOLUME_SPIKE_RATIO"] = merged_today["TOTTRDQTY"] / merged_today["VOL_5D_AVG"]
        vol_spikes = (
            merged_today.sort_values("VOLUME_SPIKE_RATIO", ascending=False)
            .head(10)[["SYMBOL", "TOTTRDQTY", "VOLUME_SPIKE_RATIO"]]
            .to_dict(orient="records")
        )

        # ✅ Turnover leaders
        turnover_leaders = (
            day_df.sort_values("TOTTRDVAL", ascending=False)
            .head(10)[["SYMBOL", "TOTTRDVAL", "TOTTRDQTY", "CLOSE"]]
            .to_dict(orient="records")
        )

        results[day_name] = {
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "volume_spikes": vol_spikes,
            "turnover_leaders": turnover_leaders
        }

    return results


def compute_symbol_correlation(df):
    """
    Symbol-level CLOSE price correlations across all dates
    """
    pivot_prices = df.pivot(index="DATE1", columns="SYMBOL", values="CLOSE")
    corr_matrix = pivot_prices.corr()

    corr_unstacked = corr_matrix.unstack().reset_index()
    corr_unstacked.columns = ["SYMBOL_A", "SYMBOL_B", "CORR"]
    corr_unstacked = corr_unstacked[corr_unstacked["SYMBOL_A"] < corr_unstacked["SYMBOL_B"]]

    top_pos = corr_unstacked.sort_values("CORR", ascending=False).head(10).to_dict(orient="records")
    top_neg = corr_unstacked.sort_values("CORR", ascending=True).head(10).to_dict(orient="records")

    return {
        "top_positive_correlations": top_pos,
        "top_negative_correlations": top_neg
    }


def generate_full_analytics():
    """
    Full pipeline:
      - Load all bhavcopies
      - Per-date analytics
      - Symbol correlations
    """
    df_all = load_all_bhavcopies()

    daily_metrics = compute_daily_metrics(df_all)
    correlations = compute_symbol_correlation(df_all)

    return {
        "available_dates": sorted(list(df_all["DATE1"].dt.strftime("%Y-%m-%d").unique())),
        "daily_metrics": daily_metrics,
        "correlations": correlations
    }
