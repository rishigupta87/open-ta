# 🎯 OI Signal Trading System

A comprehensive real-time options trading system built with Open Interest (OI) analysis and Implied Volatility (IV) monitoring.

## 🚀 System Architecture

### Core Components
1. **OI Signal Engine** - Real-time analysis of OI changes with IV filtering
2. **TimescaleDB Storage** - Hypertable-optimized time-series data storage  
3. **GraphQL API** - Admin interface for signal management
4. **Streamlit Dashboard** - Real-time signal monitoring UI
5. **Market Hours Manager** - Exchange-specific trading time management

### Trading Hours Support
- **MCX**: 9:00 AM - 11:30 PM IST (Commodities)
- **NSE/NFO**: 9:20 AM - 3:30 PM IST (Equity & Options)

## 📊 Signal Generation Criteria

### Primary Filters
- **Minimum IV**: 15% threshold
- **OI Change Analysis**: 5-minute intervals
- **Strike Selection**: Nearest 5 calls/puts per underlying
- **Underlying Assets**: NIFTY, BANKNIFTY, CRUDEOIL, NATURALGAS

### Signal Strength Classification
- **STRONG**: OI change ≥20%, IV ≥15%, Min absolute OI change 1000
- **MEDIUM**: OI change ≥10%, IV ≥15%
- **WEAK**: Below medium thresholds

### Signal Types
- **BULLISH**: Call buying OR Put selling OR Long futures buildup
- **BEARISH**: Put buying OR Call selling OR Short covering
- **NEUTRAL**: Mixed or low-impact changes

## 🗄️ Database Schema

### OI Signals Table (`oi_signals`)
```sql
- timestamp (TIMESTAMPTZ, hypertable partition key)
- token, symbol, underlying
- current_oi, previous_oi, oi_change, oi_change_percent
- current_price, implied_volatility
- signal_strength (STRONG/MEDIUM/WEAK)
- signal_type (BULLISH/BEARISH/NEUTRAL)
- exchange, instrument_type, option_type
- strike_price, analysis_window
```

### OI Analytics Table (`oi_analytics`)
```sql
- timestamp (TIMESTAMPTZ, hypertable partition key)
- underlying (NIFTY, BANKNIFTY, etc.)
- call_oi_change, put_oi_change
- max_call_oi_change, max_put_oi_change
- avg_iv, max_iv, high_iv_count
- pcr_oi (Put-Call Ratio by OI)
- market_sentiment, sentiment_score
```

## 🔧 API Endpoints

### GraphQL Queries
```graphql
# Get current real-time signals
getCurrentSignals(limit: Int!): OISignalResponse

# Get historical signals with filters
getOiSignals(
  limit: Int = 50
  signalStrength: String
  underlying: String
  exchange: String
): OISignalResponse

# Get aggregated analytics
getOiAnalytics(limit: Int = 10, underlying: String): OIAnalyticsResponse

# Check market status
getMarketStatus: MarketStatusResponse

# Get signal engine status
getSignalEngineStatus: SignalEngineResponse
```

### GraphQL Mutations
```graphql
# Setup database tables
setupOiTables: SignalEngineResponse

# Control signal engine
startOiSignalEngine: SignalEngineResponse
stopOiSignalEngine: SignalEngineResponse

# Streaming controls
startEnhancedStreaming(category: String): StreamingResponse
stopEnhancedStreaming(category: String): StreamingResponse
```

## 🖥️ Admin Dashboard Features

### Real-time Monitoring
- **Market Status**: Live exchange status and trading hours
- **Signal Engine**: Start/stop engine with status monitoring
- **Active Signals**: Top 10 real-time signals with filtering
- **Auto-refresh**: 30-second automatic updates

### Signal Analysis
- **OI Change Distribution**: Histogram of OI percentage changes
- **IV vs OI Scatter**: Correlation between volatility and OI changes
- **Market Sentiment**: Bullish/bearish signal distribution
- **PCR Analysis**: Put-Call Ratio trends

### Filtering Options
- Signal strength (STRONG/MEDIUM/WEAK)
- Signal type (BULLISH/BEARISH/NEUTRAL)
- Underlying asset filter
- Exchange filter

## 🚀 Quick Start Guide

### 1. Start the System
```bash
# Build and start all services
docker-compose -f docker-compose.yml -f docker-compose.debug.yml up -d

# Setup OI tables (one-time)
curl -X POST -H "Content-Type: application/json" \
  -d '{"query":"mutation { setupOiTables { success message } }"}' \
  http://localhost:8000/graphql
```

### 2. Initialize Data Pipeline
```bash
# Sync trading instruments
curl -X POST -H "Content-Type: application/json" \
  -d '{"query":"mutation { syncInstruments(forceRefresh: true) { success message } }"}' \
  http://localhost:8000/graphql

# Start enhanced streaming
curl -X POST -H "Content-Type: application/json" \
  -d '{"query":"mutation { startEnhancedStreaming { success message } }"}' \
  http://localhost:8000/graphql
```

### 3. Start Signal Engine
```bash
# Start OI signal analysis
curl -X POST -H "Content-Type: application/json" \
  -d '{"query":"mutation { startOiSignalEngine { success message } }"}' \
  http://localhost:8000/graphql
```

### 4. Access Admin Dashboard
- **Frontend URL**: http://localhost:8501
- **Navigate to**: Admin Dashboard
- **GraphQL Playground**: http://localhost:8000/graphql

## 📈 Signal Interpretation

### High-Priority Signals
1. **STRONG + BULLISH**: Heavy call buying or put selling with high IV
2. **STRONG + BEARISH**: Heavy put buying or call selling with high IV
3. **High OI % Change**: >20% change in 5-minute window
4. **High IV**: >15% implied volatility threshold

### Market Context Indicators
- **PCR > 1.2**: Bearish sentiment (more put activity)
- **PCR < 0.8**: Bullish sentiment (more call activity)
- **High IV Count**: Market uncertainty/volatility spike
- **Sentiment Score**: -1 (Bearish) to +1 (Bullish)

## ⚠️ Risk Management

### Signal Validation
- Confirm with underlying price movement
- Check volume alongside OI changes
- Consider time decay for options
- Monitor market-wide sentiment

### Position Sizing
- Use signal strength for position allocation
- Limit exposure during high IV periods
- Consider correlation between underlyings
- Set stop-losses based on signal invalidation

## 🔧 Configuration

### Signal Thresholds (Customizable)
```python
thresholds = {
    'min_iv': 15.0,              # Minimum IV percentage
    'strong_oi_change': 20.0,    # Strong signal OI change %
    'medium_oi_change': 10.0,    # Medium signal OI change %
    'min_oi_absolute': 1000,     # Minimum absolute OI change
    'analysis_window': 300,      # 5 minutes in seconds
}
```

### Trading Hours Configuration
```python
trading_hours = {
    'MCX': {'start': time(9, 0), 'end': time(23, 30)},
    'NSE': {'start': time(9, 20), 'end': time(15, 30)},
    'NFO': {'start': time(9, 20), 'end': time(15, 30)}
}
```

## 📊 Performance Metrics

### System Capabilities
- **Real-time Processing**: 5-minute analysis cycles
- **Token Coverage**: Current month futures + nearest 5 options
- **Data Retention**: Configurable (default 30 days)
- **Signal Latency**: <30 seconds from market data receipt
- **Concurrent Users**: Optimized for multiple dashboard viewers

### Monitoring
- Signal generation rate
- Database performance metrics
- API response times
- Market data streaming health
- System resource utilization

---

## 🎯 Success Criteria

The system successfully generates actionable trading signals when:
1. **OI changes** exceed defined thresholds with **high IV**
2. **Market hours** are properly respected for each exchange
3. **Real-time updates** reflect current market conditions
4. **Admin dashboard** provides clear signal visualization
5. **API responses** deliver sub-second performance

This comprehensive OI signal system provides professional-grade options trading intelligence with institutional-quality real-time analytics.
