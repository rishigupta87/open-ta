from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .timescale_models import Base
import os
import logzero

logger = logzero.logger


def create_timescale_engine():
    """Create TimescaleDB engine"""
    database_url = os.getenv("DATABASE_URL", "postgresql://trading:trading123@timescaledb:5432/trading_data")
    engine = create_engine(database_url, echo=False)
    return engine


def setup_timescaledb():
    """Setup TimescaleDB with hypertables and functions"""
    try:
        engine = create_timescale_engine()
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Created all TimescaleDB tables")
        
        # Create TimescaleDB hypertables
        with engine.connect() as conn:
            # Enable TimescaleDB extension
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))
                logger.info("TimescaleDB extension enabled")
            except Exception as e:
                logger.warning(f"TimescaleDB extension may already exist: {e}")
            
            # Create hypertables for time-series data
            hypertable_queries = [
                """
                SELECT create_hypertable(
                    'market_data_ticks', 
                    'timestamp',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '1 hour'
                );
                """,
                """
                SELECT create_hypertable(
                    'trading_signals', 
                    'timestamp',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '1 day'
                );
                """,
                """
                SELECT create_hypertable(
                    'options_flow', 
                    'timestamp',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '1 hour'
                );
                """,
                """
                SELECT create_hypertable(
                    'crudeoil_analytics', 
                    'timestamp',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '15 minutes'
                );
                """,
                """
                SELECT create_hypertable(
                    'trade_executions', 
                    'timestamp',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '1 day'
                );
                """
            ]
            
            for query in hypertable_queries:
                try:
                    conn.execute(text(query))
                    logger.info(f"Created hypertable: {query.split('(')[1].split(',')[0].strip().replace("'", '')}")
                except Exception as e:
                    logger.warning(f"Hypertable may already exist: {e}")
            
            # Create continuous aggregates for real-time analytics
            continuous_agg_queries = [
                """
                CREATE MATERIALIZED VIEW IF NOT EXISTS crude_oil_1min_candles
                WITH (timescaledb.continuous) AS
                SELECT 
                    time_bucket('1 minute', timestamp) AS bucket,
                    token,
                    symbol,
                    FIRST(ltp, timestamp) AS open,
                    MAX(ltp) AS high,
                    MIN(ltp) AS low,
                    LAST(ltp, timestamp) AS close,
                    SUM(volume) AS volume,
                    LAST(oi, timestamp) AS oi,
                    COUNT(*) AS tick_count
                FROM market_data_ticks 
                WHERE symbol LIKE '%CRUDE%'
                GROUP BY bucket, token, symbol;
                """,
                """
                CREATE MATERIALIZED VIEW IF NOT EXISTS crude_oil_5min_candles
                WITH (timescaledb.continuous) AS
                SELECT 
                    time_bucket('5 minutes', timestamp) AS bucket,
                    token,
                    symbol,
                    FIRST(ltp, timestamp) AS open,
                    MAX(ltp) AS high,
                    MIN(ltp) AS low,
                    LAST(ltp, timestamp) AS close,
                    SUM(volume) AS volume,
                    LAST(oi, timestamp) AS oi,
                    AVG(ltp) AS avg_price,
                    STDDEV(ltp) AS price_volatility
                FROM market_data_ticks 
                WHERE symbol LIKE '%CRUDE%'
                GROUP BY bucket, token, symbol;
                """,
                """
                CREATE MATERIALIZED VIEW IF NOT EXISTS signal_summary_hourly
                WITH (timescaledb.continuous) AS
                SELECT 
                    time_bucket('1 hour', timestamp) AS bucket,
                    signal_type,
                    action,
                    COUNT(*) AS signal_count,
                    AVG(strength) AS avg_strength,
                    COUNT(*) FILTER (WHERE executed = true) AS executed_count
                FROM trading_signals
                GROUP BY bucket, signal_type, action;
                """
            ]
            
            for query in continuous_agg_queries:
                try:
                    conn.execute(text(query))
                    view_name = query.split('VIEW IF NOT EXISTS ')[1].split('\n')[0].strip()
                    logger.info(f"Created continuous aggregate: {view_name}")
                except Exception as e:
                    logger.warning(f"Continuous aggregate may already exist: {e}")
            
            # Create real-time analytics functions
            function_queries = [
                """
                CREATE OR REPLACE FUNCTION get_crude_oil_realtime_stats()
                RETURNS TABLE (
                    current_price NUMERIC,
                    price_change NUMERIC,
                    price_change_pct NUMERIC,
                    volume_24h BIGINT,
                    oi_change NUMERIC,
                    support_level NUMERIC,
                    resistance_level NUMERIC,
                    sentiment_score NUMERIC
                ) AS $$
                BEGIN
                    RETURN QUERY
                    WITH recent_data AS (
                        SELECT 
                            ltp,
                            volume,
                            oi,
                            oi_change,
                            timestamp,
                            LAG(ltp) OVER (ORDER BY timestamp) AS prev_ltp
                        FROM market_data_ticks 
                        WHERE symbol LIKE '%CRUDE%FUT' 
                        AND timestamp > NOW() - INTERVAL '1 day'
                        ORDER BY timestamp DESC
                        LIMIT 1000
                    ),
                    price_stats AS (
                        SELECT 
                            FIRST_VALUE(ltp) OVER (ORDER BY timestamp DESC) AS current_ltp,
                            PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY ltp) AS support,
                            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY ltp) AS resistance,
                            SUM(volume) AS total_volume,
                            AVG(oi_change) AS avg_oi_change
                        FROM recent_data
                    )
                    SELECT 
                        ps.current_ltp::NUMERIC,
                        (ps.current_ltp - LAG(ps.current_ltp) OVER ())::NUMERIC AS change,
                        ((ps.current_ltp - LAG(ps.current_ltp) OVER ()) / LAG(ps.current_ltp) OVER () * 100)::NUMERIC AS change_pct,
                        ps.total_volume::BIGINT,
                        ps.avg_oi_change::NUMERIC,
                        ps.support::NUMERIC,
                        ps.resistance::NUMERIC,
                        CASE 
                            WHEN ps.avg_oi_change > 0 THEN 0.7
                            WHEN ps.avg_oi_change < 0 THEN 0.3
                            ELSE 0.5
                        END::NUMERIC AS sentiment
                    FROM price_stats ps
                    LIMIT 1;
                END;
                $$ LANGUAGE plpgsql;
                """,
                """
                CREATE OR REPLACE FUNCTION get_active_trading_signals(minutes_back INTEGER DEFAULT 60)
                RETURNS TABLE (
                    signal_id TEXT,
                    timestamp TIMESTAMPTZ,
                    symbol TEXT,
                    signal_type TEXT,
                    action TEXT,
                    strength NUMERIC,
                    trigger_price NUMERIC,
                    reason TEXT
                ) AS $$
                BEGIN
                    RETURN QUERY
                    SELECT 
                        ts.id,
                        ts.timestamp,
                        ts.symbol,
                        ts.signal_type,
                        ts.action,
                        ts.strength,
                        ts.trigger_price,
                        ts.reason
                    FROM trading_signals ts
                    WHERE ts.timestamp > NOW() - (minutes_back || ' minutes')::INTERVAL
                    AND ts.is_active = true
                    ORDER BY ts.timestamp DESC;
                END;
                $$ LANGUAGE plpgsql;
                """
            ]
            
            for query in function_queries:
                try:
                    conn.execute(text(query))
                    func_name = query.split('FUNCTION ')[1].split('(')[0]
                    logger.info(f"Created function: {func_name}")
                except Exception as e:
                    logger.warning(f"Function may already exist: {e}")
            
            conn.commit()
            logger.info("TimescaleDB setup completed successfully")
            
    except Exception as e:
        logger.error(f"Error setting up TimescaleDB: {e}")
        raise


def get_timescale_session():
    """Get TimescaleDB session"""
    engine = create_timescale_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


# Analytics queries
class TimescaleAnalytics:
    """Real-time analytics using TimescaleDB"""
    
    def __init__(self):
        self.engine = create_timescale_engine()
    
    def get_crude_oil_realtime_data(self):
        """Get real-time crude oil analytics"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT * FROM get_crude_oil_realtime_stats();"))
                return result.fetchone()
        except Exception as e:
            logger.error(f"Error getting real-time data: {e}")
            return None
    
    def get_recent_candles(self, minutes=60):
        """Get recent OHLC candles"""
        try:
            query = """
            SELECT 
                bucket,
                open,
                high,
                low,
                close,
                volume,
                oi
            FROM crude_oil_1min_candles 
            WHERE bucket > NOW() - INTERVAL '%s minutes'
            ORDER BY bucket DESC;
            """ % minutes
            
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                return result.fetchall()
        except Exception as e:
            logger.error(f"Error getting candles: {e}")
            return []
    
    def get_active_signals(self, minutes=60):
        """Get active trading signals"""
        try:
            query = "SELECT * FROM get_active_trading_signals(%s);" % minutes
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                return result.fetchall()
        except Exception as e:
            logger.error(f"Error getting signals: {e}")
            return []


# Global analytics instance
timescale_analytics = TimescaleAnalytics()
