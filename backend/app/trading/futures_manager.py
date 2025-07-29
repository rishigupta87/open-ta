from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..db.models import TradingInstrument
from ..db.operations import get_db
import logzero
from datetime import datetime

logger = logzero.logger


class FuturesManager:
    """Manager for current month futures tokens and streaming setup"""
    
    def __init__(self):
        self.current_futures: Dict[str, Dict] = {}
        self.streaming_tokens: Dict[str, str] = {}
    
    def get_current_month_futures(self, commodity: str = "CRUDEOIL") -> Optional[Dict]:
        """Get current month futures for a commodity"""
        try:
            db = get_db()
            try:
                # Get all futures for the commodity
                futures = db.query(TradingInstrument).filter(
                    and_(
                        TradingInstrument.name == commodity,
                        TradingInstrument.instrumenttype == "FUTCOM",
                        TradingInstrument.exch_seg == "MCX"
                    )
                ).all()
                
                if not futures:
                    logger.error(f"No futures found for {commodity}")
                    return None
                
                # Parse expiry dates and find the nearest one
                from datetime import datetime
                today = datetime.now()
                current_month_year = today.strftime("%b%Y").upper()  # e.g., "JUL2025"
                
                # First try to find current month futures
                current_month_future = None
                for future in futures:
                    if current_month_year in future.expiry:
                        current_month_future = future
                        break
                
                # If no current month, find the nearest future month
                if not current_month_future:
                    # Sort by expiry date (convert to datetime for proper sorting)
                    def parse_expiry_date(expiry_str):
                        try:
                            # Parse formats like "21JUL2025" or "19AUG2025"
                            return datetime.strptime(expiry_str, "%d%b%Y")
                        except:
                            # Fallback for other formats
                            return datetime.strptime(expiry_str[-7:], "%b%Y")
                    
                    futures_with_dates = []
                    for future in futures:
                        try:
                            date_obj = parse_expiry_date(future.expiry)
                            if date_obj >= today:  # Only future dates
                                futures_with_dates.append((future, date_obj))
                        except:
                            continue
                    
                    if not futures_with_dates:
                        logger.error(f"No valid future expiry dates found for {commodity}")
                        return None
                    
                    # Sort by date and get the nearest
                    futures_with_dates.sort(key=lambda x: x[1])
                    current_month_future = futures_with_dates[0][0]
                
                current_future = current_month_future
                
                future_data = {
                    "token": current_future.token,
                    "symbol": current_future.symbol,
                    "name": current_future.name,
                    "expiry": current_future.expiry,
                    "lotsize": current_future.lotsize,
                    "exchange": current_future.exch_seg,
                    "updated_at": datetime.now()
                }
                
                # Cache it
                self.current_futures[commodity] = future_data
                
                logger.info(f"Current month {commodity} futures: {current_future.symbol} (Token: {current_future.token})")
                return future_data
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting current month futures for {commodity}: {e}")
            return None
    
    def store_streaming_token(self, commodity: str, token: str) -> bool:
        """Store token for streaming"""
        try:
            self.streaming_tokens[commodity] = token
            logger.info(f"Stored streaming token for {commodity}: {token}")
            return True
        except Exception as e:
            logger.error(f"Error storing streaming token: {e}")
            return False
    
    def get_streaming_token(self, commodity: str) -> Optional[str]:
        """Get stored streaming token"""
        return self.streaming_tokens.get(commodity)
    
    def setup_commodity_streaming(self, commodity: str = "CRUDEOIL") -> Dict:
        """Setup streaming for a commodity's current month futures"""
        try:
            # Get current month futures
            futures_data = self.get_current_month_futures(commodity)
            
            if not futures_data:
                return {
                    "success": False,
                    "message": f"Could not find current month futures for {commodity}"
                }
            
            # Store the token for streaming
            token = futures_data["token"]
            success = self.store_streaming_token(commodity, token)
            
            if success:
                return {
                    "success": True,
                    "message": f"Setup streaming for {commodity}",
                    "futures_data": futures_data,
                    "streaming_token": token
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to store streaming token for {commodity}"
                }
                
        except Exception as e:
            logger.error(f"Error setting up commodity streaming: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    def get_all_active_tokens(self) -> List[str]:
        """Get all active streaming tokens"""
        return list(self.streaming_tokens.values())
    
    def get_commodity_info(self, commodity: str) -> Optional[Dict]:
        """Get complete commodity information"""
        if commodity in self.current_futures:
            return {
                "futures": self.current_futures[commodity],
                "streaming_token": self.streaming_tokens.get(commodity),
                "is_active": commodity in self.streaming_tokens
            }
        return None

    def get_commodity_option_tokens(self, commodity: str = "CRUDEOIL") -> List[str]:
        """Get all option tokens for a commodity"""
        try:
            db = get_db()
            try:
                from ..db.timescale_models import TradingInstrument
                
                # Get current month futures first
                futures = db.query(TradingInstrument).filter(
                    and_(
                        TradingInstrument.name == commodity,
                        TradingInstrument.instrumenttype == "FUTCOM",
                        TradingInstrument.exch_seg == "MCX"
                    )
                ).order_by(TradingInstrument.expiry).first()
                
                if not futures:
                    return []
                
                # Get all options for the same expiry
                options = db.query(TradingInstrument).filter(
                    and_(
                        TradingInstrument.name == commodity,
                        TradingInstrument.instrumenttype == "OPTFUT",
                        TradingInstrument.expiry == futures.expiry,
                        TradingInstrument.exch_seg == "MCX"
                    )
                ).all()
                
                return [opt.token for opt in options]
                
            finally:
                db.close()
                
        except Exception as e:
            logzero.logger.error(f"Failed to get commodity option tokens: {e}")
            return []


# Global instance
futures_manager = FuturesManager()
