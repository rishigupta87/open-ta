import streamlit as st
import json
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="📊 Stock Bhavcopy Analytics", layout="wide")
st.title("📈 Stock Market Analytics Dashboard")

# === File Upload ===
uploaded_file = st.file_uploader("📂 Upload JSON analytics file", type=["json"])

if uploaded_file is None:
    st.info("Upload your **bhavcopy analytics JSON** to view insights.")
    st.stop()

# === Load JSON ===
try:
    analytics_raw = json.load(uploaded_file)
    analytics = analytics_raw["analytics"]  # our structure
    dates = sorted(analytics.keys())
except Exception as e:
    st.error(f"❌ Failed to parse JSON: {e}")
    st.stop()

# === Sidebar Date Selection ===
st.sidebar.header("Filters")
selected_dates = st.sidebar.multiselect(
    "Select Dates",
    dates,
    default=[dates[-1]]  # latest date selected by default
)

if not selected_dates:
    st.warning("⚠️ Please select at least one date")
    st.stop()

# === Prepare a combined trend dataframe ===
trend_data = []
for d in selected_dates:
    d_data = analytics[d]
    trend_data.append({
        "date": d,
        "advancers": d_data["advancers"],
        "decliners": d_data["decliners"],
        "median_delivery": d_data["median_delivery"]
    })
trend_df = pd.DataFrame(trend_data)

# === Tabs ===
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Market Breadth & Trends",
    "🚀 Gainers & Losers",
    "📦 Delivery & Turnover",
    "🏭 Sector & Segment Insights"
])

# =======================================================
# ✅ TAB 1: Market Breadth & Trendline
# =======================================================
with tab1:
    st.header("📈 Market Breadth & Median Delivery Trend")

    # ✅ Show pie chart for last selected date
    last_date = selected_dates[-1]
    last_day_data = analytics[last_date]

    st.subheader(f"📅 Market Breadth on {last_date}")
    pie_df = pd.DataFrame({
        "Category": ["Advancers", "Decliners"],
        "Count": [last_day_data["advancers"], last_day_data["decliners"]]
    })
    fig_pie = px.pie(pie_df, names="Category", values="Count", title=f"Market Breadth on {last_date}")
    st.plotly_chart(fig_pie, use_container_width=True)

    # ✅ Trendline for all selected dates
    st.subheader("📊 Trend Over Selected Dates")
    trend_long = trend_df.melt(
        id_vars="date", 
        value_vars=["advancers", "decliners", "median_delivery"],
        var_name="Metric", 
        value_name="Value"
    )
    fig_trend = px.line(
        trend_long, x="date", y="Value", color="Metric", markers=True,
        title="Advancers vs Decliners vs Median Delivery %"
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# =======================================================
# ✅ TAB 2: Top Gainers & Losers
# =======================================================
with tab2:
    st.header(f"🚀 Top Gainers & 📉 Losers ({last_date})")

    gainers_df = pd.DataFrame(last_day_data["top_gainers"])
    losers_df = pd.DataFrame(last_day_data["top_losers"])

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🚀 Top Gainers")
        st.dataframe(gainers_df)
        fig_gainers = px.bar(
            gainers_df.head(10),
            x="SYMBOL", y="PCT_CHANGE",
            title=f"Top 10 Gainers ({last_date})",
            color="PCT_CHANGE"
        )
        st.plotly_chart(fig_gainers, use_container_width=True)

    with col2:
        st.subheader("📉 Top Losers")
        st.dataframe(losers_df)
        fig_losers = px.bar(
            losers_df.head(10),
            x="SYMBOL", y="PCT_CHANGE",
            title=f"Top 10 Losers ({last_date})",
            color="PCT_CHANGE",
            color_continuous_scale="reds"
        )
        st.plotly_chart(fig_losers, use_container_width=True)

# =======================================================
# ✅ TAB 3: Delivery & Turnover Insights
# =======================================================
with tab3:
    st.header(f"📦 Delivery & Turnover Insights ({last_date})")

    # High Delivery
    st.subheader("📦 High Delivery Stocks (>70%)")
    high_delivery_df = pd.DataFrame(last_day_data["high_delivery"])
    st.dataframe(high_delivery_df)

    # Turnover Leaders
    st.subheader("💰 Turnover Leaders")
    turnover_df = pd.DataFrame(last_day_data["turnover_leaders"])
    st.dataframe(turnover_df)
    fig_turnover = px.bar(turnover_df.head(10), x="SYMBOL", y="TURNOVER_LACS", title="Top Turnover Stocks")
    st.plotly_chart(fig_turnover, use_container_width=True)

    # Volatility Spikes
    st.subheader("⚡ Intraday Volatility Spikes")
    vol_df = pd.DataFrame(last_day_data["volatility_spikes"])
    st.dataframe(vol_df)
    fig_vol = px.bar(vol_df.head(10), x="SYMBOL", y="INTRADAY_VOL", title="High Intraday Volatility (%)")
    st.plotly_chart(fig_vol, use_container_width=True)

# =======================================================
# ✅ TAB 4: Sector & Segment Insights
# =======================================================
with tab4:
    st.header(f"🏭 Sector & Segment Insights ({last_date})")

    # Sector Delivery %
    sector_delivery = last_day_data.get("sector_delivery", {})
    if sector_delivery:
        sector_df = pd.DataFrame(list(sector_delivery.items()), columns=["Sector", "Avg Delivery %"])
        fig_sector = px.bar(
            sector_df.sort_values("Avg Delivery %", ascending=False),
            x="Sector", y="Avg Delivery %",
            title="Sector-wise Avg Delivery %"
        )
        st.plotly_chart(fig_sector, use_container_width=True)
    else:
        st.info("No sector data available.")

    # Segment Stats
    st.subheader("💹 Segment Stats (Cash vs F&O)")
    seg_stats = last_day_data.get("segment_stats", {})
    if seg_stats:
        seg_df = pd.DataFrame(seg_stats).T.reset_index().rename(columns={"index": "Segment"})
        st.dataframe(seg_df)

        fig_seg = px.bar(seg_df, x="Segment", y="median_delivery",
                        title="Median Delivery % by Segment", color="Segment")
        st.plotly_chart(fig_seg, use_container_width=True)
    else:
        st.info("No segment stats available.")
