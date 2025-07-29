"""TimescaleDB operations for real-time market data"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from datetime import datetime
import logzero

from .models import MarketData
from .database import engine

logger = logzero.logger


def create_hypertable(db: Session):
    """Create TimescaleDB hypertable for market_data"""
    try:
        # Check if hypertable already exists
        check_sql = """
        SELECT EXISTS (
            SELECT 1 FROM timescaledb_information.hypertables 
            WHERE hypertable_name = 'market_data'
        );
        """
        result = db.execute(text(check_sql)).scalar()
        
        if not result:
            # Create hypertable
            hypertable_sql = """
            SELECT create_hypertable('market_data', 'timestamp', 
                                    chunk_time_interval => INTERVAL '1 hour',
                                    if_not_exists => TRUE);
            """
            db.execute(text(hypertable_sql))
            db.commit()
            logger.info("Created TimescaleDB hypertable for market_data")
        else:
            logger.info("TimescaleDB hypertable for market_data already exists")
            
    except Exception as e:
        logger.error(f"Error creating hypertable: {e}")
        db.rollback()
        raise


def create_market_data_indexes(db: Session):
    """Create additional indexes for better query performance"""
    try:
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_market_data_token_time ON market_data (token, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data (symbol, timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_market_data_exchange_time ON market_data (exchange, timestamp DESC);"
        ]
        
        for index_sql in indexes:
            db.execute(text(index_sql))
            
        db.commit()
        logger.info("Created additional indexes for market_data")
        
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        db.rollback()
        raise


def insert_market_data_batch(db: Session, market_data_list: List[Dict[str, Any]]) -> int:
    """Bulk insert market data efficiently"""
    try:
        inserted_count = 0
        
        for data in market_data_list:
            market_data = MarketData(
                token=str(data.get('token', '')),
                symbol=data.get('symbol', ''),
                timestamp=data.get('timestamp', datetime.utcnow()),
                open_price=data.get('open_price'),
                high_price=data.get('high_price'),
                low_price=data.get('low_price'),
                close_price=data.get('close_price'),
                ltp=data.get('ltp', 0.0),
                volume=data.get('volume'),
                oi=data.get('oi'),
                oi_change=data.get('oi_change'),
                bid_price=data.get('bid_price'),
                ask_price=data.get('ask_price'),
                bid_qty=data.get('bid_qty'),
                ask_qty=data.get('ask_qty'),
                exchange=data.get('exchange', ''),
                instrument_type=data.get('instrument_type', '')
            )
            db.add(market_data)
            inserted_count += 1
        
        db.commit()
        logger.info(f"Inserted {inserted_count} market data records")
        return inserted_count
        
    except Exception as e:
        logger.error(f"Error inserting market data: {e}")
        db.rollback()
        raise


def get_latest_market_data(db: Session, token: str, limit: int = 100) -> List[MarketData]:
    """Get latest market data for a specific token"""
    try:
        return db.query(MarketData).filter(
            MarketData.token == token
        ).order_by(MarketData.timestamp.desc()).limit(limit).all()
        
    except Exception as e:
        logger.error(f"Error fetching latest market data: {e}")
        raise


def get_market_data_time_range(
    db: Session, 
    token: str, 
    start_time: datetime, 
    end_time: datetime
) -> List[MarketData]:
    """Get market data for a token within a time range"""
    try:
        return db.query(MarketData).filter(
            MarketData.token == token,
            MarketData.timestamp >= start_time,
            MarketData.timestamp <= end_time
        ).order_by(MarketData.timestamp).all()
        
    except Exception as e:
        logger.error(f"Error fetching market data for time range: {e}")
        raise


def get_ohlcv_aggregated(
    db: Session,
    token: str,
    interval: str = "1m",  # 1m, 5m, 15m, 1h, 1d
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get OHLCV data aggregated by time interval"""
    try:
        # Map interval to PostgreSQL interval
        interval_map = {
            "1m": "1 minute",
            "5m": "5 minutes", 
            "15m": "15 minutes",
            "1h": "1 hour",
            "1d": "1 day"
        }
        
        pg_interval = interval_map.get(interval, "1 minute")
        
        # Build time bucket query
        query = f"""
        SELECT 
            time_bucket('{pg_interval}', timestamp) as time_bucket,
            token,
            symbol,
            FIRST(ltp, timestamp) as open,
            MAX(ltp) as high,
            MIN(ltp) as low,
            LAST(ltp, timestamp) as close,
            SUM(volume) as volume,
            LAST(oi, timestamp) as oi,
            exchange,
            instrument_type
        FROM market_data
        WHERE token = :token
        """
        
        if start_time:
            query += " AND timestamp >= :start_time"
        if end_time:
            query += " AND timestamp <= :end_time"
            
        query += """
        GROUP BY time_bucket, token, symbol, exchange, instrument_type
        ORDER BY time_bucket DESC
        LIMIT :limit
        """
        
        params = {"token": token, "limit": limit}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
            
        result = db.execute(text(query), params)
        
        return [dict(row) for row in result]
        
    except Exception as e:
        logger.error(f"Error fetching OHLCV aggregated data: {e}")
        raise


def cleanup_old_market_data(db: Session, days_to_keep: int = 30) -> int:
    """Clean up old market data to manage storage"""
    try:
        cutoff_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date - timedelta(days=days_to_keep)
        
        deleted_count = db.query(MarketData).filter(
            MarketData.timestamp < cutoff_date
        ).delete(synchronize_session=False)
        
        db.commit()
        logger.info(f"Cleaned up {deleted_count} old market data records")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error cleaning up old market data: {e}")
        db.rollback()
        raise


def get_market_data_stats(db: Session) -> Dict[str, Any]:
    """Get statistics about market data storage"""
    try:
        # Total records
        total_records = db.query(MarketData).count()
        
        # Count by exchange
        exchange_stats = db.query(
            MarketData.exchange,
            db.func.count(MarketData.id)
        ).group_by(MarketData.exchange).all()
        
        # Count by instrument type
        type_stats = db.query(
            MarketData.instrument_type,
            db.func.count(MarketData.id)
        ).group_by(MarketData.instrument_type).all()
        
        # Latest timestamp
        latest_timestamp = db.query(
            db.func.max(MarketData.timestamp)
        ).scalar()
        
        return {
            "total_records": total_records,
            "by_exchange": dict(exchange_stats),
            "by_instrument_type": dict(type_stats),
            "latest_timestamp": latest_timestamp
        }
        
    except Exception as e:
        logger.error(f"Error getting market data stats: {e}")
        raise
