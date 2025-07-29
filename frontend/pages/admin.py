"""Admin dashboard for OI signals and trading analytics"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
import traceback
import json

# Try to import plotly, fallback to basic charts if not available
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("Plotly not available. Using basic charts.")

# Setup logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Debug mode toggle
DEBUG_MODE = st.sidebar.checkbox("🐛 Debug Mode", value=False, help="Enable detailed debugging information")

# Debug utilities
def debug_function(func_name, *args, **kwargs):
    """Debug function calls"""
    if DEBUG_MODE:
        st.write(f"🔍 **Debug: Calling {func_name}**")
        if args:
            st.write(f"Args: {args}")
        if kwargs:
            st.write(f"Kwargs: {kwargs}")
        logger.debug(f"Calling {func_name} with args={args}, kwargs={kwargs}")

def debug_variable(var_name, value):
    """Debug variable values"""
    if DEBUG_MODE:
        st.write(f"🔍 **Debug Variable: {var_name}**")
        if isinstance(value, (dict, list)):
            st.json(value)
        else:
            st.code(str(value))
        logger.debug(f"{var_name} = {value}")

def debug_breakpoint(label="Breakpoint", data=None):
    """Interactive debugging breakpoint"""
    if DEBUG_MODE:
        st.write(f"🔍 **Debug Breakpoint: {label}**")
        if data:
            st.write("Data:", data)
        
        # Interactive debugging options
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📊 Inspect Data", key=f"inspect_{hash(label)}"):
                if data:
                    st.json(data)
                else:
                    st.info("No data available")
        
        with col2:
            if st.button("📝 View Logs", key=f"logs_{hash(label)}"):
                st.text("Check container logs with: docker-compose logs frontend")
        
        with col3:
            if st.button("▶️ Continue", key=f"continue_{hash(label)}"):
                st.success("Continuing execution...")
        
        logger.debug(f"Breakpoint hit: {label}")

# Configure page
st.set_page_config(
    page_title="Open-TA Admin Dashboard",
    page_icon="📊",
    layout="wide"
)

# GraphQL endpoint
GRAPHQL_ENDPOINT = "http://backend:8000/graphql"

def execute_graphql_query(query, variables=None):
    """Execute GraphQL query with debugging support"""
    try:
        # Debug logging
        if DEBUG_MODE:
            st.write("🔍 **Debug: GraphQL Query**")
            with st.expander("Query Details", expanded=False):
                st.code(query, language="graphql")
                if variables:
                    st.write("Variables:", variables)
                st.write(f"Endpoint: {GRAPHQL_ENDPOINT}")
        
        logger.debug(f"Executing GraphQL query to {GRAPHQL_ENDPOINT}")
        logger.debug(f"Query: {query}")
        logger.debug(f"Variables: {variables}")
        
        # Add debugging breakpoint capability
        if DEBUG_MODE and st.button("🐛 Set Breakpoint Here", key=f"breakpoint_{hash(query)}"):
            st.info("🔍 **Breakpoint Hit**: GraphQL Query Execution")
            st.write("**Query:**", query)
            st.write("**Variables:**", variables or {})
            st.write("**Endpoint:**", GRAPHQL_ENDPOINT)
            
            # Allow user to continue or modify
            if st.button("▶️ Continue Execution"):
                pass
        
        response = requests.post(
            GRAPHQL_ENDPOINT,
            json={"query": query, "variables": variables or {}},
            timeout=10
        )
        
        # Debug response
        if DEBUG_MODE:
            st.write(f"🔍 **Debug: Response Status**: {response.status_code}")
            if response.status_code != 200:
                st.error(f"HTTP Error: {response.status_code}")
                st.code(response.text)
        
        response.raise_for_status()
        result = response.json()
        
        # Debug response content
        if DEBUG_MODE:
            with st.expander("Response Details", expanded=False):
                st.json(result)
        
        logger.debug(f"Response status: {response.status_code}")
        logger.debug(f"Response: {result}")
        
        # Check for GraphQL errors
        if "errors" in result:
            error_msg = f"GraphQL Errors: {result['errors']}"
            st.error(error_msg)
            logger.error(error_msg)
            
            if DEBUG_MODE:
                st.write("🔍 **Debug: GraphQL Errors**")
                for i, error in enumerate(result['errors']):
                    st.write(f"Error {i+1}:", error)
            return None
            
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network Error: {e}"
        st.error(error_msg)
        logger.error(error_msg)
        
        if DEBUG_MODE:
            st.write("🔍 **Debug: Network Error Details**")
            st.code(traceback.format_exc())
        return None
        
    except Exception as e:
        error_msg = f"Unexpected Error: {e}"
        st.error(error_msg)
        logger.error(error_msg)
        
        if DEBUG_MODE:
            st.write("🔍 **Debug: Exception Details**")
            st.code(traceback.format_exc())
        return None

def get_market_status():
    """Get current market status"""
    debug_function("get_market_status")
    
    query = """
    query {
        getMarketStatus {
            success
            message
            activeExchanges
            tradingHours
            currentTimeIst
            currentDay
            isTradingDay
            isAnyMarketOpen
            statusReason
            nextTradingDay
            daysUntilNextTrading
        }
    }
    """
    
    result = execute_graphql_query(query)
    debug_variable("market_status_result", result)
    
    return result

def get_signal_engine_status():
    """Get signal engine status"""
    query = """
    query {
        getSignalEngineStatus {
            success
            message
            status {
                isRunning
                activeExchanges
                currentSignalsCount
                lastAnalysisTime
                analysisInterval
            }
        }
    }
    """
    return execute_graphql_query(query)

def get_current_signals(limit=20):
    """Get current real-time signals"""
    query = """
    query GetCurrentSignals($limit: Int!) {
        getCurrentSignals(limit: $limit) {
            success
            message
            signals {
                timestamp
                symbol
                underlying
                oiChange
                oiChangePercent
                impliedVolatility
                signalStrength
                signalType
                currentPrice
                strikePrice
                optionType
                exchange
            }
            totalCount
        }
    }
    """
    return execute_graphql_query(query, {"limit": limit})

def get_oi_analytics(limit=10, underlying=None):
    """Get OI analytics"""
    query = """
    query GetOIAnalytics($limit: Int!, $underlying: String) {
        getOiAnalytics(limit: $limit, underlying: $underlying) {
            success
            message
            analytics {
                timestamp
                underlying
                totalOiChange
                callOiChange
                putOiChange
                maxCallOiChange
                maxPutOiChange
                avgIv
                maxIv
                highIvCount
                pcrOi
                marketSentiment
                sentimentScore
                exchange
            }
            totalCount
        }
    }
    """
    return execute_graphql_query(query, {"limit": limit, "underlying": underlying})

def start_signal_engine():
    """Start OI signal engine"""
    query = """
    mutation {
        startOiSignalEngine {
            success
            message
        }
    }
    """
    return execute_graphql_query(query)

def stop_signal_engine():
    """Stop OI signal engine"""
    query = """
    mutation {
        stopOiSignalEngine {
            success
            message
        }
    }
    """
    return execute_graphql_query(query)

def setup_oi_tables():
    """Setup OI tables"""
    query = """
    mutation {
        setupOiTables {
            success
            message
        }
    }
    """
    return execute_graphql_query(query)

def main():
    st.title("🎯 Open-TA Admin Dashboard")
    st.markdown("Real-time OI Analysis & Trading Signals")
    
    debug_function("main")
    
    # Enhanced debug information
    if DEBUG_MODE:
        st.markdown("### 🔍 **Debug Information Panel**")
        
        col1, col2 = st.columns(2)
        with col1:
            st.code(f"GraphQL Endpoint: {GRAPHQL_ENDPOINT}")
            st.code(f"Plotly Available: {PLOTLY_AVAILABLE}")
            st.code(f"Debug Mode: {DEBUG_MODE}")
        
        with col2:
            # Test connectivity with debugging
            try:
                test_response = requests.get("http://backend:8000/", timeout=5)
                st.success(f"✅ Backend connectivity: {test_response.status_code}")
                debug_variable("backend_response", test_response.headers)
            except Exception as e:
                st.error(f"❌ Backend connectivity failed: {e}")
                debug_variable("connectivity_error", str(e))
        
        # Add debugging controls
        st.markdown("### 🛠️ **Debug Controls**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔍 Test GraphQL Connection"):
                debug_breakpoint("GraphQL Connection Test", {"endpoint": GRAPHQL_ENDPOINT})
        
        with col2:
            if st.button("📊 Dump Session State"):
                debug_variable("session_state", dict(st.session_state))
        
        with col3:
            if st.button("🚫 Clear Debug Cache"):
                st.cache_data.clear()
                st.success("Debug cache cleared!")
    
    # Standard debug information (always visible)
    with st.expander("🔧 Debug Information", expanded=False):
        st.code(f"GraphQL Endpoint: {GRAPHQL_ENDPOINT}")
        st.code(f"Plotly Available: {PLOTLY_AVAILABLE}")
        
        # Test connectivity
        try:
            test_response = requests.get("http://backend:8000/", timeout=5)
            st.success(f"✅ Backend connectivity: {test_response.status_code}")
        except Exception as e:
            st.error(f"❌ Backend connectivity failed: {e}")
    
    # Sidebar for controls
    with st.sidebar:
        st.header("🔧 Controls")
        
        # Debug section first if enabled
        if DEBUG_MODE:
            st.markdown("### 🐛 **Debug Dashboard**")
            
            # Real-time debugging
            debug_level = st.selectbox(
                "Debug Level",
                ["INFO", "DEBUG", "WARNING", "ERROR"],
                index=1
            )
            logger.setLevel(getattr(logging, debug_level))
            
            # Function tracing
            trace_functions = st.checkbox("🔍 Trace Function Calls", value=False)
            if trace_functions:
                st.info("Function tracing enabled")
            
            # Performance monitoring
            if st.button("⏱️ Performance Check"):
                import time
                start_time = time.time()
                test_result = get_market_status()
                end_time = time.time()
                st.metric("API Response Time", f"{(end_time - start_time):.2f}s")
                debug_variable("performance_test", test_result)
            
            # Memory usage
            try:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                st.metric("Memory Usage", f"{memory_usage:.1f} MB")
            except ImportError:
                st.caption("psutil not available for memory monitoring")
            
            st.divider()
        
        # Setup tables
        if st.button("Setup OI Tables", type="secondary"):
            debug_function("setup_oi_tables_button_clicked")
            with st.spinner("Setting up tables..."):
                result = setup_oi_tables()
                debug_variable("setup_tables_result", result)
                if result and result.get("data", {}).get("setupOiTables", {}).get("success"):
                    st.success("Tables setup successfully!")
                else:
                    st.error("Failed to setup tables")
        
        st.divider()
        
        # Signal engine controls
        st.subheader("Signal Engine")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("▶️ Start", key="start_engine"):
                debug_function("start_signal_engine_button_clicked")
                result = start_signal_engine()
                debug_variable("start_engine_result", result)
                if result and result.get("data", {}).get("startOiSignalEngine", {}).get("success"):
                    st.success("Engine started!")
                else:
                    st.error("Failed to start engine")
        
        with col2:
            if st.button("⏹️ Stop", key="stop_engine"):
                debug_function("stop_signal_engine_button_clicked")
                result = stop_signal_engine()
                debug_variable("stop_engine_result", result)
                if result and result.get("data", {}).get("stopOiSignalEngine", {}).get("success"):
                    st.success("Engine stopped!")
                else:
                    st.error("Failed to stop engine")
        
        st.divider()
        
        # Refresh controls
        auto_refresh = st.checkbox("Auto Refresh (30s)", value=True)
        
        if st.button("🔄 Refresh Now"):
            debug_function("refresh_button_clicked")
            st.rerun()
    
    # Connection status check
    st.markdown("### 🔌 System Status")
    try:
        # Quick health check
        health_response = requests.get("http://backend:8000/", timeout=5)
        if health_response.status_code == 200:
            st.success("✅ Backend connection: OK")
        else:
            st.warning(f"⚠️ Backend returned status: {health_response.status_code}")
    except Exception as e:
        st.error(f"❌ Backend connection failed: {str(e)}")
        st.info("💡 Make sure the backend service is running")
    
    # Main dashboard content
    # Market Status Section
    st.header("📈 Market Status")
    
    debug_breakpoint("Market Status Section Start")
    
    market_status = get_market_status()
    engine_status = get_signal_engine_status()
    
    debug_variable("market_status_response", market_status)
    debug_variable("engine_status_response", engine_status)
    
    if market_status and engine_status:
        market_data = market_status.get("data", {}).get("getMarketStatus", {})
        engine_data = engine_status.get("data", {}).get("getSignalEngineStatus", {})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            is_open = market_data.get("isAnyMarketOpen", False)
            is_trading_day = market_data.get("isTradingDay", False)
            current_day = market_data.get("currentDay", "")
            current_time = market_data.get("currentTimeIst", "")
            status_reason = market_data.get("statusReason", "")
            
            # Market status with weekday info
            if is_open:
                status_text = f"🟢 OPEN ({current_day})"
            elif not is_trading_day:
                status_text = f"🔴 WEEKEND ({current_day})"
            else:
                status_text = f"🔴 CLOSED ({current_day})"
            
            st.metric(
                "Market Status", 
                status_text,
                delta=current_time
            )
            
            # Show detailed status reason
            st.caption(f"📝 {status_reason}")
            
            # Show next trading day info if weekend
            if not is_trading_day:
                next_trading_day = market_data.get("nextTradingDay", "")
                days_until = market_data.get("daysUntilNextTrading", 0)
                if days_until > 0:
                    st.info(f"📅 Next trading day: {next_trading_day} ({days_until} day{'s' if days_until > 1 else ''} away)")
            elif not is_open:
                st.info("⏰ Markets are currently closed")
                st.caption("Trading Hours (Mon-Fri):")
                st.caption("MCX: 9:00 AM - 11:30 PM IST")
                st.caption("NSE/NFO: 9:20 AM - 3:30 PM IST")
        
        with col2:
            active_exchanges = market_data.get("activeExchanges", [])
            st.metric(
                "Active Exchanges",
                len(active_exchanges),
                delta=", ".join(active_exchanges) if active_exchanges else "None"
            )
            
            if not active_exchanges:
                st.caption("No exchanges currently active")
        
        with col3:
            engine_running = engine_data.get("status", {}).get("isRunning", False)
            st.metric(
                "Signal Engine",
                "🟢 RUNNING" if engine_running else "🔴 STOPPED"
            )
            
            if not engine_running and not is_open:
                st.caption("Engine idle - markets closed")
        
        with col4:
            signal_count = engine_data.get("status", {}).get("currentSignalsCount", 0)
            st.metric(
                "Active Signals",
                signal_count
            )
            
            if signal_count == 0 and not is_open:
                st.caption("No signals - markets closed")
    else:
        st.error("Unable to fetch market status. Please check backend connection.")
    
    # Real-time Signals Section
    st.header("🚨 Real-time OI Signals")
    
    # Check if markets are open before trying to get signals
    is_market_open = False
    is_trading_day = False
    status_reason = ""
    
    if market_status and market_status.get("data") and market_status["data"].get("getMarketStatus"):
        market_info = market_status["data"]["getMarketStatus"]
        is_market_open = market_info.get("isAnyMarketOpen", False)
        is_trading_day = market_info.get("isTradingDay", False)
        status_reason = market_info.get("statusReason", "")
    
    if not is_market_open:
        if not is_trading_day:
            # Weekend message
            st.info("🗓️ Weekend - Markets are closed on weekends.")
            next_trading_day = market_info.get("nextTradingDay", "Monday") if market_info else "Monday"
            days_until = market_info.get("daysUntilNextTrading", 0) if market_info else 0
            if days_until > 0:
                st.markdown(f"📅 **Next trading day**: {next_trading_day} ({days_until} day{'s' if days_until > 1 else ''} away)")
        else:
            # Weekday but outside trading hours
            st.info("🔔 Markets are currently closed. No real-time signals available.")
        
        st.markdown("""
        **Trading Hours (Monday - Friday):**
        - **MCX**: 9:00 AM - 11:30 PM IST
        - **NSE/NFO**: 9:20 AM - 3:30 PM IST
        """)
    else:
        signals_data = get_current_signals(20)
        
        if signals_data and signals_data.get("data", {}).get("getCurrentSignals", {}).get("success"):
            signals = signals_data["data"]["getCurrentSignals"]["signals"]
            
            if signals:
                # Convert to DataFrame
                df_signals = pd.DataFrame(signals)
                df_signals['timestamp'] = pd.to_datetime(df_signals['timestamp'])
            
                # Filter controls
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    strength_filter = st.selectbox(
                        "Signal Strength",
                        ["All", "STRONG", "MEDIUM", "WEAK"],
                        index=0
                    )
                
                with col2:
                    type_filter = st.selectbox(
                        "Signal Type", 
                        ["All", "BULLISH", "BEARISH", "NEUTRAL"],
                        index=0
                    )
                
                with col3:
                    underlying_filter = st.selectbox(
                        "Underlying",
                        ["All"] + list(df_signals['underlying'].unique()),
                        index=0
                    )
            
                # Apply filters
                filtered_df = df_signals.copy()
                if strength_filter != "All":
                    filtered_df = filtered_df[filtered_df['signalStrength'] == strength_filter]
                if type_filter != "All":
                    filtered_df = filtered_df[filtered_df['signalType'] == type_filter]
                if underlying_filter != "All":
                    filtered_df = filtered_df[filtered_df['underlying'] == underlying_filter]
                
                # Display signals table
                st.dataframe(
                    filtered_df[['timestamp', 'symbol', 'underlying', 'oiChangePercent', 
                               'impliedVolatility', 'signalStrength', 'signalType', 'currentPrice']],
                    use_container_width=True,
                    hide_index=True
                )
            
                # Visualization
                if PLOTLY_AVAILABLE and len(filtered_df) > 0:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # OI Change Distribution
                        fig_oi = px.histogram(
                            filtered_df, 
                            x='oiChangePercent',
                            color='signalStrength',
                            title="OI Change % Distribution",
                            nbins=20
                        )
                        st.plotly_chart(fig_oi, use_container_width=True)
                    
                    with col2:
                        # IV vs OI Change Scatter
                        fig_scatter = px.scatter(
                            filtered_df,
                            x='impliedVolatility',
                            y='oiChangePercent',
                            color='signalType',
                            size='currentPrice',
                            hover_data=['symbol', 'underlying'],
                            title="IV vs OI Change"
                        )
                        st.plotly_chart(fig_scatter, use_container_width=True)
                elif len(filtered_df) > 0:
                    # Fallback to basic charts
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("OI Change % Distribution")
                        try:
                            st.bar_chart(filtered_df['oiChangePercent'])
                        except Exception as e:
                            st.error(f"Chart error: {e}")
                    
                    with col2:
                        st.subheader("Signal Strength Distribution")
                        try:
                            strength_counts = filtered_df['signalStrength'].value_counts()
                            st.bar_chart(strength_counts)
                        except Exception as e:
                            st.error(f"Chart error: {e}")
                else:
                    st.info("No signals to visualize")
            else:
                st.info("No real-time signals available during market hours")
        else:
            st.error("Failed to fetch signals. Please check backend connection.")
    
    # Market Analytics Section
    st.header("📊 Market Analytics")
    
    analytics_data = get_oi_analytics(10)
    
    if analytics_data and analytics_data.get("data", {}).get("getOiAnalytics", {}).get("success"):
        analytics = analytics_data["data"]["getOiAnalytics"]["analytics"]
        
        if analytics:
            df_analytics = pd.DataFrame(analytics)
            df_analytics['timestamp'] = pd.to_datetime(df_analytics['timestamp'])
            
            # Market sentiment overview
            col1, col2, col3, col4 = st.columns(4)
            
            latest_analytics = df_analytics.iloc[0] if len(df_analytics) > 0 else {}
            
            with col1:
                st.metric(
                    "Call OI Change",
                    f"{latest_analytics.get('callOiChange', 0):,}",
                    delta=f"{latest_analytics.get('maxCallOiChange', 0):,} (Max)"
                )
            
            with col2:
                st.metric(
                    "Put OI Change", 
                    f"{latest_analytics.get('putOiChange', 0):,}",
                    delta=f"{latest_analytics.get('maxPutOiChange', 0):,} (Max)"
                )
            
            with col3:
                st.metric(
                    "PCR (OI)",
                    f"{latest_analytics.get('pcrOi', 0):.2f}",
                    delta=latest_analytics.get('marketSentiment', 'NEUTRAL')
                )
            
            with col4:
                st.metric(
                    "Avg IV",
                    f"{latest_analytics.get('avgIv', 0):.1f}%",
                    delta=f"{latest_analytics.get('highIvCount', 0)} High IV"
                )
            
            # Analytics charts
            if PLOTLY_AVAILABLE and len(df_analytics) > 0:
                col1, col2 = st.columns(2)
                
                with col1:
                    # OI Changes Trend
                    fig_trend = go.Figure()
                    fig_trend.add_trace(go.Scatter(
                        x=df_analytics['timestamp'],
                        y=df_analytics['callOiChange'],
                        name='Call OI Change',
                        line=dict(color='green')
                    ))
                    fig_trend.add_trace(go.Scatter(
                        x=df_analytics['timestamp'],
                        y=df_analytics['putOiChange'],
                        name='Put OI Change',
                        line=dict(color='red')
                    ))
                    fig_trend.update_layout(title="OI Changes Trend")
                    st.plotly_chart(fig_trend, use_container_width=True)
                
                with col2:
                    # Market Sentiment
                    sentiment_counts = df_analytics['marketSentiment'].value_counts()
                    fig_sentiment = px.pie(
                        values=sentiment_counts.values,
                        names=sentiment_counts.index,
                        title="Market Sentiment Distribution"
                    )
                    st.plotly_chart(fig_sentiment, use_container_width=True)
            elif len(df_analytics) > 0:
                # Fallback to basic charts
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("OI Changes Trend")
                    chart_data = df_analytics[['callOiChange', 'putOiChange']].copy()
                    chart_data.index = df_analytics['timestamp']
                    st.line_chart(chart_data)
                
                with col2:
                    st.subheader("Market Sentiment")
                    sentiment_counts = df_analytics['marketSentiment'].value_counts()
                    st.bar_chart(sentiment_counts)
            else:
                st.info("No analytics data to visualize")
        else:
            st.info("No analytics data available")
    
    # Auto-refresh functionality
    if auto_refresh:
        time.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
