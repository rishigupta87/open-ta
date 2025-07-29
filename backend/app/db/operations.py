import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
import requests
import json
import logzero
import calendar

logger = logzero.logger

def get_current_month_expiry_range():
    """Get the date range for current month expiries"""
    now = datetime.now()
    # Get first and last day of current month
    first_day = now.replace(day=1)
    last_day = now.replace(day=calendar.monthrange(now.year, now.month)[1])
    return first_day, last_day

def get_atm_strike_price(df: pd.DataFrame, underlying_name: str) -> float:
    """
    Get ATM (At The Money) strike price for an underlying
    This is a simplified version - you might want to fetch live prices
    """
    # For now, return median strike price as approximation
    # In production, you'd fetch current market price of underlying
    strikes = df[df['name'] == underlying_name]['strike'].dropna()
    if len(strikes) > 0:
        return strikes.median()
    return 0.0

def filter_nearest_strikes(df: pd.DataFrame, atm_strike: float, num_strikes: int = 5) -> pd.DataFrame:
    """
    Filter options to keep only nearest N strike prices around ATM
    """
    if atm_strike == 0.0 or df.empty:
        return df
    
    # Calculate distance from ATM for each strike
    df = df.copy()
    df['strike_distance'] = abs(df['strike'] - atm_strike)
    
    # Get unique strikes sorted by distance from ATM
    unique_strikes = df.groupby('strike')['strike_distance'].first().nsmallest(num_strikes).index
    
    # Filter dataframe to keep only these strikes
    filtered_df = df[df['strike'].isin(unique_strikes)].copy()
    filtered_df = filtered_df.drop('strike_distance', axis=1)
    
    return filtered_df

def fetch_and_process_nse_instruments_filtered() -> pd.DataFrame:
    """
    Fetch and process NSE instruments with filtering for:
    - Current month futures only
    - Nearest 5 strikes for options
    """
    try:
        logger.info("Fetching and processing NSE instruments with filtering...")
        
        # Fetch raw data
        url = 'https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json'
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Filter for NFO instruments (options and futures)
        filtered_df = df[(df['exch_seg'] == 'NFO') & 
                        (df['instrumenttype'].isin(['FUTSTK', 'OPTSTK', 'FUTIDX', 'OPTIDX']))]
        
        # Remove test records
        filtered_df = filtered_df[~filtered_df['name'].str.contains('test', case=False, na=False)]
        
        # Process expiry dates
        filtered_df['expiry'] = filtered_df.apply(_extract_expiry_nse, axis=1)
        filtered_df['expiry'] = pd.to_datetime(filtered_df['expiry'], errors='coerce')
        
        # Remove rows with invalid expiry dates
        filtered_df = filtered_df.dropna(subset=['expiry'])
        
        # Get current month date range
        first_day, last_day = get_current_month_expiry_range()
        
        # Separate futures and options for different processing
        futures_df = filtered_df[filtered_df['instrumenttype'].isin(['FUTSTK', 'FUTIDX'])].copy()
        options_df = filtered_df[filtered_df['instrumenttype'].isin(['OPTSTK', 'OPTIDX'])].copy()
        
        # Process Futures - Keep only current month expiries
        logger.info("Processing futures - filtering for current month expiries...")
        futures_df = futures_df[
            (futures_df['expiry'] >= first_day) & 
            (futures_df['expiry'] <= last_day)
        ]
        
        # For futures, keep only the nearest expiry for each underlying
        futures_df = futures_df.groupby(['name', 'instrumenttype']).apply(
            lambda x: x.nsmallest(1, 'expiry')
        ).reset_index(drop=True)
        
        # Process Options - Keep current month + nearest 5 strikes
        logger.info("Processing options - filtering for current month and nearest 5 strikes...")
        options_df = options_df[
            (options_df['expiry'] >= first_day) & 
            (options_df['expiry'] <= last_day)
        ]
        
        # Process strike prices for options
        options_df['strike'] = pd.to_numeric(options_df['strike'], errors='coerce')
        options_df['strike'] = (options_df['strike'] / 100).round(2)
        
        # Process call/put information
        options_df['call_put'] = options_df.apply(_extract_strike_price_nse, axis=1)
        options_df['call_put'] = options_df['call_put'].apply(_clean_strike_price)
        
        # Filter options to nearest 5 strikes for each underlying and expiry
        filtered_options_list = []
        
        for (name, expiry), group in options_df.groupby(['name', 'expiry']):
            logger.info(f"Processing options for {name} expiry {expiry.strftime('%Y-%m-%d')}")
            
            # Get ATM strike price (you might want to fetch live price here)
            atm_strike = get_atm_strike_price(group, name)
            
            # Filter to nearest 5 strikes
            filtered_group = filter_nearest_strikes(group, atm_strike, num_strikes=5)
            filtered_options_list.append(filtered_group)
        
        # Combine filtered options
        if filtered_options_list:
            options_df = pd.concat(filtered_options_list, ignore_index=True)
        else:
            options_df = pd.DataFrame()
        
        # Process futures strike and call_put
        if not futures_df.empty:
            futures_df['strike'] = 0.0
            futures_df['call_put'] = futures_df['symbol']
        
        # Combine futures and options
        final_df = pd.concat([futures_df, options_df], ignore_index=True)
        
        # Add metadata
        final_df['timestamp'] = datetime.now()
        final_df['data_source'] = 'NSE'
        final_df['filter_applied'] = 'current_month_nearest_5_strikes'
        
        logger.info(f"NSE filtering completed: {len(futures_df)} futures, {len(options_df)} options")
        return final_df
        
    except Exception as e:
        logger.error(f"Error processing NSE instruments: {e}")
        raise

def fetch_and_process_mcx_instruments_filtered() -> pd.DataFrame:
    """
    Fetch and process MCX instruments with filtering for:
    - Current month futures only
    - Nearest 5 strikes for options
    """
    try:
        logger.info("Fetching and processing MCX instruments with filtering...")
        
        # Fetch raw data
        url = 'https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json'
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Filter for specific MCX commodities
        specific_names = ['CRUDEOIL', 'NATURALGAS']
        filtered_df = df[(df['exch_seg'] == 'MCX') & 
                        (df['name'].isin(specific_names)) & 
                        (df['instrumenttype'].isin(['FUTCOM', 'OPTFUT']))]
        
        # Remove test records
        filtered_df = filtered_df[~filtered_df['name'].str.contains('test', case=False, na=False)]
        
        # Process expiry dates
        filtered_df['expiry'] = filtered_df.apply(_extract_expiry_mcx, axis=1)
        filtered_df['expiry'] = pd.to_datetime(filtered_df['expiry'], errors='coerce')
        
        # Remove rows with invalid expiry dates
        filtered_df = filtered_df.dropna(subset=['expiry'])
        
        # Get current month date range
        first_day, last_day = get_current_month_expiry_range()
        
        # Separate futures and options
        futures_df = filtered_df[filtered_df['instrumenttype'] == 'FUTCOM'].copy()
        options_df = filtered_df[filtered_df['instrumenttype'] == 'OPTFUT'].copy()
        
        # Process Futures - Keep only current month expiries
        logger.info("Processing MCX futures - filtering for current month expiries...")
        futures_df = futures_df[
            (futures_df['expiry'] >= first_day) & 
            (futures_df['expiry'] <= last_day)
        ]
        
        # For futures, keep only the nearest expiry for each commodity
        futures_df = futures_df.groupby(['name', 'instrumenttype']).apply(
            lambda x: x.nsmallest(1, 'expiry')
        ).reset_index(drop=True)
        
        # Process Options - Keep current month + nearest 5 strikes
        logger.info("Processing MCX options - filtering for current month and nearest 5 strikes...")
        options_df = options_df[
            (options_df['expiry'] >= first_day) & 
            (options_df['expiry'] <= last_day)
        ]
        
        # Process strike and call/put for options
        if not options_df.empty:
            strike_callput_data = options_df.apply(_extract_strike_and_call_put_mcx, axis=1)
            options_df[['strike', 'call_put']] = pd.DataFrame(
                strike_callput_data.tolist(), index=options_df.index
            )
            
            # Filter options to nearest 5 strikes for each commodity and expiry
            filtered_options_list = []
            
            for (name, expiry), group in options_df.groupby(['name', 'expiry']):
                logger.info(f"Processing MCX options for {name} expiry {expiry.strftime('%Y-%m-%d')}")
                
                # Get ATM strike price
                atm_strike = get_atm_strike_price(group, name)
                
                # Filter to nearest 5 strikes
                filtered_group = filter_nearest_strikes(group, atm_strike, num_strikes=5)
                filtered_options_list.append(filtered_group)
            
            # Combine filtered options
            if filtered_options_list:
                options_df = pd.concat(filtered_options_list, ignore_index=True)
            else:
                options_df = pd.DataFrame()
        
        # Process futures strike and call_put
        if not futures_df.empty:
            futures_df['strike'] = 0.0
            futures_df['call_put'] = futures_df['symbol']
        
        # Combine futures and options
        final_df = pd.concat([futures_df, options_df], ignore_index=True)
        
        # Add metadata
        final_df['timestamp'] = datetime.now()
        final_df['data_source'] = 'MCX'
        final_df['filter_applied'] = 'current_month_nearest_5_strikes'
        
        logger.info(f"MCX filtering completed: {len(futures_df)} futures, {len(options_df)} options")
        return final_df
        
    except Exception as e:
        logger.error(f"Error processing MCX instruments: {e}")
        raise

def bulk_upsert_filtered_instruments(db: Session, instruments_df: pd.DataFrame) -> Dict[str, int]:
    """
    Bulk insert/update filtered instruments in database
    """
    try:
        stats = {"inserted": 0, "updated": 0, "errors": 0, "skipped": 0}
        
        logger.info(f"Processing {len(instruments_df)} filtered instruments...")
        
        for idx, row in instruments_df.iterrows():
            try:
                # Check if instrument already exists
                existing = db.query(TradingInstrument).filter(
                    TradingInstrument.token == row["token"]
                ).first()
                
                # Prepare data
                instrument_data = {
                    'token': row['token'],
                    'symbol': row.get('symbol', ''),
                    'name': row['name'],
                    'expiry': row.get('expiry'),
                    'strike': float(row.get('strike', 0.0)) if pd.notna(row.get('strike')) else None,
                    'lotsize': int(row.get('lotsize', 1)),
                    'instrumenttype': row['instrumenttype'],
                    'exch_seg': row['exch_seg'],
                    'tick_size': float(row.get('tick_size', 0.0)),
                }
                
                if existing:
                    # Update existing record
                    for key, value in instrument_data.items():
                        if key != 'token':  # Don't update token
                            setattr(existing, key, value)
                    stats["updated"] += 1
                else:
                    # Create new record
                    new_instrument = TradingInstrument(**instrument_data)
                    db.add(new_instrument)
                    stats["inserted"] += 1
                
                # Commit every 500 records
                if (idx + 1) % 500 == 0:
                    db.commit()
                    logger.info(f"Processed {idx + 1}/{len(instruments_df)} filtered instruments")
                    
            except Exception as e:
                logger.error(f"Error processing instrument {row.get('token', 'unknown')}: {e}")
                stats["errors"] += 1
                continue
        
        # Final commit
        db.commit()
        logger.info(f"Filtered bulk upsert completed: {stats}")
        return stats
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during filtered bulk upsert: {e}")
        raise

def fetch_and_store_filtered_instruments(db: Session) -> Dict[str, Any]:
    """
    Main function to fetch, filter, and store instruments with current month futures 
    and nearest 5 strikes for options
    """
    try:
        logger.info("Starting filtered instrument processing pipeline...")
        
        results = {
            "nse_stats": {},
            "mcx_stats": {},
            "total_processed": 0,
            "filter_criteria": {
                "futures": "current_month_only",
                "options": "current_month_nearest_5_strikes"
            },
            "timestamp": datetime.now()
        }
        
        # Clear existing data first (optional)
        logger.info("Clearing existing instrument data...")
        db.query(TradingInstrument).delete()
        db.commit()
        
        # Process NSE instruments with filtering
        nse_df = fetch_and_process_nse_instruments_filtered()
        nse_stats = bulk_upsert_filtered_instruments(db, nse_df)
        results["nse_stats"] = nse_stats
        
        # Process MCX instruments with filtering
        mcx_df = fetch_and_process_mcx_instruments_filtered()
        mcx_stats = bulk_upsert_filtered_instruments(db, mcx_df)
        results["mcx_stats"] = mcx_stats
        
        results["total_processed"] = len(nse_df) + len(mcx_df)
        
        logger.info(f"Complete processing finished: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error in complete processing pipeline: {e}")
        raise

# Helper functions (extracted from the original scripts)
def _extract_expiry_nse(row):
    """Extract expiry date for NSE instruments"""
    if pd.isna(row['expiry']) or row['expiry'] == '':
        try:
            expiry_str = row['name'][-7:]
            return pd.to_datetime(expiry_str, format='%d%b%y', errors='coerce')
        except:
            return pd.NaT
    else:
        return pd.to_datetime(row['expiry'], errors='coerce')

def _extract_expiry_mcx(row):
    """Extract expiry date for MCX instruments"""
    if pd.isna(row['expiry']) or row['expiry'] == '':
        try:
            if row['instrumenttype'] == 'FUTCOM':
                expiry_str = row['symbol'][len(row['name']):len(row['name']) + 5]
            else:
                expiry_str = row['symbol'][len(row['name']):len(row['name']) + 5]
            return pd.to_datetime(expiry_str, format='%d%b', errors='coerce').replace(year=datetime.now().year)
        except:
            return pd.NaT
    else:
        return pd.to_datetime(row['expiry'], errors='coerce')

def _get_nearest_expiries_nse(group, instrumenttype):
    """Get nearest expiries for NSE instruments"""
    if 'FUT' in instrumenttype:
        nearest_expiries = group['expiry'].nsmallest(2)
    else:
        nearest_expiries = group['expiry'].nsmallest(1)
    return group[group['expiry'].isin(nearest_expiries)]

def _get_nearest_expiries_mcx(group, instrumenttype):
    """Get nearest expiries for MCX instruments"""
    if instrumenttype == 'FUTCOM':
        nearest_expiries = group['expiry'].nsmallest(2)
    else:
        nearest_expiry = group['expiry'].nsmallest(1)
        nearest_expiries = nearest_expiry if not nearest_expiry.empty else pd.Series([pd.NaT])
    return group[group['expiry'].isin(nearest_expiries)]

def _extract_strike_price_nse(row):
    """Extract strike price for NSE instruments"""
    if row['instrumenttype'] in ['OPTSTK', 'OPTIDX']:
        parts = row['symbol'].split(row['expiry'].strftime('%d%b%y').upper())
        if len(parts) > 1:
            return parts[1]
        else:
            return row['symbol']
    else:
        return row['symbol']

def _clean_strike_price(sp):
    """Clean strike price string"""
    return ''.join([i for i in sp if not i.isdigit()])

def _extract_strike_and_call_put_mcx(row):
    """Extract strike and call/put for MCX options"""
    if row['instrumenttype'] == 'OPTFUT':
        parts = row['symbol'][len(row['name']) + 5:]
        strike_part = ''.join([c for c in parts if c.isdigit() or c == '.'])
        call_put = parts.replace(strike_part, '')
        return float(strike_part) if strike_part else 0.0, call_put
    else:
        return 0.0, row['symbol']


# Additional imports for complete functionality
from .models import TradingInstrument
from .database import SessionLocal, engine, Base


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def fetch_instruments_from_api() -> List[Dict[str, Any]]:
    """Fetch instrument data from AngelOne API"""
    url = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
    
    try:
        logger.info("Fetching instruments data from AngelOne API...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Successfully fetched {len(data)} instruments")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching instruments data: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON response: {e}")
        raise

#Relevant
def filter_instruments_for_trading(instruments_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter instruments to keep only NSE, NFO, and specific MCX commodities"""
    filtered = []
    
    for instrument in instruments_data:
        exch_seg = instrument.get("exch_seg", "")
        name = instrument.get("name", "")
        instrument_type = instrument.get("instrumenttype", "")
        
        # Keep NSE and NFO instruments
        if exch_seg in ["NFO"] and instrument_type in ["FUTSTK", "OPTSTK", "FUTIDX", "OPTIDX"]:
            filtered.append(instrument)
        # Keep specific MCX commodities
        elif exch_seg == "MCX" and name in ["CRUDEOIL", "NATURALGAS"] and instrument_type in ["FUTCOM", "OPTCOM"]:
            filtered.append(instrument)
    
    logger.info(f"Filtered {len(filtered)} instruments from {len(instruments_data)} total")
    return filtered


def bulk_upsert_instruments(db: Session, instruments_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """Bulk insert/update filtered instruments in database"""
    try:
        stats = {"inserted": 0, "updated": 0, "errors": 0, "filtered_out": 0}
        
        # Filter instruments before processing
        filtered_instruments = filter_instruments_for_trading(instruments_data)
        stats["filtered_out"] = len(instruments_data) - len(filtered_instruments)
        
        logger.info(f"Processing {len(filtered_instruments)} filtered instruments...")
        
        for idx, instrument_data in enumerate(filtered_instruments):
            try:
                # Check if instrument already exists
                existing = db.query(TradingInstrument).filter(
                    TradingInstrument.token == instrument_data["token"]
                ).first()
                
                # Parse numeric fields safely
                strike = float(instrument_data.get("strike", "0.0") or "0.0")
                lotsize = int(instrument_data.get("lotsize", "1") or "1")
                tick_size = float(instrument_data.get("tick_size", "0.0") or "0.0")
                
                if existing:
                    # Update existing record - HOT RELOAD TEST
                    existing.symbol = instrument_data["symbol"]
                    existing.name = instrument_data["name"]
                    existing.expiry = instrument_data.get("expiry") or None
                    existing.strike = strike if strike > 0 else None
                    existing.lotsize = lotsize
                    existing.instrumenttype = instrument_data["instrumenttype"]
                    existing.exch_seg = instrument_data["exch_seg"]
                    existing.tick_size = tick_size
                    stats["updated"] += 1
                else:
                    # Create new record
                    new_instrument = TradingInstrument(
                        token=instrument_data["token"],
                        symbol=instrument_data["symbol"],
                        name=instrument_data["name"],
                        expiry=instrument_data.get("expiry") or None,
                        strike=strike if strike > 0 else None,
                        lotsize=lotsize,
                        instrumenttype=instrument_data["instrumenttype"],
                        exch_seg=instrument_data["exch_seg"],
                        tick_size=tick_size
                    )
                    db.add(new_instrument)
                    stats["inserted"] += 1
                
                # Commit every 1000 records
                if (idx + 1) % 1000 == 0:
                    db.commit()
                    logger.info(f"Processed {idx + 1}/{len(filtered_instruments)} instruments")
                    
            except Exception as e:
                logger.error(f"Error processing instrument {instrument_data.get('token', 'unknown')}: {e}")
                stats["errors"] += 1
                continue
        
        # Final commit
        db.commit()
        logger.info(f"Bulk upsert completed: {stats}")
        return stats
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during bulk upsert: {e}")
        raise


def get_instruments_count(db: Session) -> int:
    """Get total count of instruments in database"""
    return db.query(TradingInstrument).count()


def get_instruments_by_exchange(db: Session, exchange: str) -> List[TradingInstrument]:
    """Get instruments by exchange"""
    return db.query(TradingInstrument).filter(
        TradingInstrument.exch_seg == exchange
    ).all()


def get_instruments_by_type(db: Session, instrument_type: str) -> List[TradingInstrument]:
    """Get instruments by type"""
    return db.query(TradingInstrument).filter(
        TradingInstrument.instrumenttype == instrument_type
    ).all()


def search_instruments(
    db: Session, 
    query: str, 
    exchange: Optional[str] = None,
    instrument_type: Optional[str] = None,
    limit: int = 100
) -> List[TradingInstrument]:
    """Search instruments by symbol or name"""
    db_query = db.query(TradingInstrument).filter(
        func.lower(TradingInstrument.symbol).contains(query.lower()) |
        func.lower(TradingInstrument.name).contains(query.lower())
    )
    
    if exchange:
        db_query = db_query.filter(TradingInstrument.exch_seg == exchange)
    
    if instrument_type:
        db_query = db_query.filter(TradingInstrument.instrumenttype == instrument_type)
    
    return db_query.limit(limit).all()


def get_instrument_stats(db: Session) -> Dict[str, Any]:
    """Get statistics about instruments in database"""
    total_count = db.query(TradingInstrument).count()
    
    # Count by exchange
    exchange_stats = db.query(
        TradingInstrument.exch_seg,
        func.count(TradingInstrument.id)
    ).group_by(TradingInstrument.exch_seg).all()
    
    # Count by instrument type
    type_stats = db.query(
        TradingInstrument.instrumenttype,
        func.count(TradingInstrument.id)
    ).group_by(TradingInstrument.instrumenttype).all()
    
    return {
        "total_instruments": total_count,
        "by_exchange": dict(exchange_stats),
        "by_type": dict(type_stats)
    }


def cleanup_instruments(db: Session) -> Dict[str, int]:
    """Clean up database to keep only NSE, NFO, and MCX crude oil/natural gas instruments"""
    try:
        logger.info("Starting instrument cleanup...")
        
        # Count before cleanup
        initial_count = db.query(TradingInstrument).count()
        
        # Delete using same filter logic
        from sqlalchemy import or_
        keep_conditions = [
            TradingInstrument.exch_seg == "NSE",
            TradingInstrument.exch_seg == "NFO",
            (TradingInstrument.exch_seg == "MCX") & 
            ((TradingInstrument.name == "CRUDEOIL") | 
             (TradingInstrument.name == "CRUDEOILM") |
             (TradingInstrument.name == "NATURALGAS") |
             (TradingInstrument.name == "BRCRUDEOIL"))
        ]
        
        keep_condition = or_(*keep_conditions)
        deleted_count = db.query(TradingInstrument).filter(~keep_condition).delete(synchronize_session=False)
        
        db.commit()
        final_count = db.query(TradingInstrument).count()
        
        logger.info(f"Cleanup completed: {initial_count} -> {final_count} instruments (deleted {deleted_count})")
        
        return {
            "initial_count": initial_count,
            "final_count": final_count,
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during cleanup: {e}")
        raise



def get_streaming_tokens_for_trading(db: Session) -> Dict[str, List[str]]:
    """Get tokens for futures and nearest 5 options (calls/puts) for streaming"""
    try:
        tokens = {"futures": [], "options_ce": [], "options_pe": []}
        
        # Get current month futures
        futures = db.query(TradingInstrument).filter(
            TradingInstrument.instrumenttype.in_(["FUTSTK", "FUTIDX", "FUTCOM"]),
            TradingInstrument.expiry >= datetime.now().date()
        ).order_by(TradingInstrument.expiry).limit(50).all()
        
        tokens["futures"] = [str(f.token) for f in futures]
        
        # Get nearest 5 options for each underlying
        underlyings = ["NIFTY", "BANKNIFTY", "CRUDEOIL", "NATURALGAS"]
        
        for underlying in underlyings:
            # Get options for this underlying
            options = db.query(TradingInstrument).filter(
                TradingInstrument.name == underlying,
                TradingInstrument.instrumenttype.in_(["OPTIDX", "OPTSTK", "OPTFUT"]),
                TradingInstrument.expiry >= datetime.now().date(),
                TradingInstrument.strike.isnot(None)
            ).order_by(TradingInstrument.expiry, TradingInstrument.strike).all()
            
            if options:
                # Group by expiry and get nearest strikes
                expiry_groups = {}
                for opt in options:
                    exp = opt.expiry
                    if exp not in expiry_groups:
                        expiry_groups[exp] = {"CE": [], "PE": []}
                    
                    if "CE" in opt.symbol:
                        expiry_groups[exp]["CE"].append(opt)
                    elif "PE" in opt.symbol:
                        expiry_groups[exp]["PE"].append(opt)
                
                # Get nearest expiry with most options
                if expiry_groups:
                    nearest_expiry = min(expiry_groups.keys())
                    nearest_options = expiry_groups[nearest_expiry]
                    
                    # Sort by strike and take nearest 5
                    ce_options = sorted(nearest_options["CE"], key=lambda x: x.strike)[:5]
                    pe_options = sorted(nearest_options["PE"], key=lambda x: x.strike)[:5]
                    
                    tokens["options_ce"].extend([str(opt.token) for opt in ce_options])
                    tokens["options_pe"].extend([str(opt.token) for opt in pe_options])
        
        logger.info(f"Generated streaming tokens: {len(tokens['futures'])} futures, {len(tokens['options_ce'])} CE, {len(tokens['options_pe'])} PE")
        return tokens
        
    except Exception as e:
        logger.error(f"Error getting streaming tokens: {e}")
        raise