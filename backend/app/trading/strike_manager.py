from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ..db.models import TradingInstrument
from ..db.operations import get_db
import logzero
from datetime import datetime

logger = logzero.logger


class StrikeManager:
    """Manager for finding and storing nearest strike options around futures price"""
    
    def __init__(self):
        self.cached_strikes: Dict[str, List[Dict]] = {}
        self.futures_tokens: Dict[str, str] = {}
    
    def get_futures_info(self, futures_token: str, db: Session) -> Optional[TradingInstrument]:
        """Get futures instrument information"""
        return db.query(TradingInstrument).filter(
            TradingInstrument.token == futures_token
        ).first()
    
    def estimate_current_price_from_strikes(self, futures_token: str, db: Session) -> Optional[float]:
        """Estimate current price by looking at available strikes (ATM estimation)"""
        try:
            # Get futures info
            futures = self.get_futures_info(futures_token, db)
            if not futures:
                return None
            
            # Get all options for the same expiry
            options = db.query(TradingInstrument).filter(
                and_(
                    TradingInstrument.name == futures.name,
                    TradingInstrument.expiry == futures.expiry,
                    TradingInstrument.instrumenttype == "OPTFUT",
                    TradingInstrument.strike.isnot(None)
                )
            ).all()
            
            if not options:
                return None
            
            # Get all unique strikes and find middle range
            strikes = sorted(list(set([opt.strike / 100 for opt in options if opt.strike])))
            
            if len(strikes) < 5:
                return None
            
            # Estimate current price as middle of available strikes range
            # For crude oil, typically trades between the available option strikes
            mid_index = len(strikes) // 2
            estimated_price = strikes[mid_index]
            
            logger.info(f"Estimated current price for {futures.symbol}: {estimated_price}")
            return estimated_price
            
        except Exception as e:
            logger.error(f"Error estimating current price: {e}")
            return None
    
    def find_nearest_strikes(
        self, 
        futures_token: str, 
        center_price: Optional[float] = None,
        num_strikes: int = 5
    ) -> Dict[str, List[Dict]]:
        """Find nearest strikes around center price for given futures"""
        try:
            db = get_db()
            try:
                # Get futures information
                futures = self.get_futures_info(futures_token, db)
                if not futures:
                    logger.error(f"Futures token {futures_token} not found")
                    return {}
                
                # If no center price provided, estimate it
                if center_price is None:
                    center_price = self.estimate_current_price_from_strikes(futures_token, db)
                    if center_price is None:
                        logger.error("Could not estimate center price")
                        return {}
                
                # Find options with same name and same month (not exact expiry)
                # Extract month/year from futures expiry (e.g., "21JUL2025" -> "JUL2025")
                if len(futures.expiry) >= 7:  # e.g., "21JUL2025"
                    futures_month_year = futures.expiry[-7:]  # "JUL2025"
                else:
                    futures_month_year = futures.expiry
                
                options = db.query(TradingInstrument).filter(
                    and_(
                        TradingInstrument.name == futures.name,
                        TradingInstrument.expiry.like(f"%{futures_month_year}"),  # Same month/year
                        TradingInstrument.instrumenttype == "OPTFUT",
                        TradingInstrument.strike.isnot(None)
                    )
                ).all()
                
                logger.info(f"Found {len(options)} options for {futures.name} {futures_month_year}")
                
                # Group by strikes
                strikes_dict = {}
                for option in options:
                    strike_price = option.strike / 100  # Convert back to actual price
                    
                    if strike_price not in strikes_dict:
                        strikes_dict[strike_price] = {"CE": None, "PE": None}
                    
                    if option.symbol.endswith("CE"):
                        strikes_dict[strike_price]["CE"] = {
                            "token": option.token,
                            "symbol": option.symbol,
                            "strike": strike_price,
                            "lotsize": option.lotsize
                        }
                    elif option.symbol.endswith("PE"):
                        strikes_dict[strike_price]["PE"] = {
                            "token": option.token,
                            "symbol": option.symbol,
                            "strike": strike_price,
                            "lotsize": option.lotsize
                        }
                
                # Find nearest strikes
                available_strikes = sorted(strikes_dict.keys())
                
                # Find strikes around center price
                nearest_strikes = []
                
                # Get strikes above and below center price
                below_strikes = [s for s in available_strikes if s <= center_price]
                above_strikes = [s for s in available_strikes if s > center_price]
                
                # Sort to get closest first
                below_strikes.sort(reverse=True)  # Closest below first
                above_strikes.sort()  # Closest above first
                
                # Build list of nearest strikes (alternating below/above)
                strikes_to_include = []
                
                # Start with ATM or nearest below
                if below_strikes:
                    strikes_to_include.append(below_strikes[0])
                
                # Add alternating strikes
                below_idx = 1 if below_strikes else 0
                above_idx = 0
                
                for _ in range(num_strikes - len(strikes_to_include)):
                    # Add above strike
                    if above_idx < len(above_strikes):
                        strikes_to_include.append(above_strikes[above_idx])
                        above_idx += 1
                    # Add below strike
                    elif below_idx < len(below_strikes):
                        strikes_to_include.append(below_strikes[below_idx])
                        below_idx += 1
                    else:
                        break
                
                # Build result
                result = {
                    "futures": {
                        "token": futures.token,
                        "symbol": futures.symbol,
                        "expiry": futures.expiry,
                        "lotsize": futures.lotsize
                    },
                    "center_price": center_price,
                    "strikes": []
                }
                
                for strike in sorted(strikes_to_include):
                    strike_data = strikes_dict[strike]
                    strike_info = {
                        "strike": strike,
                        "call": strike_data["CE"],
                        "put": strike_data["PE"]
                    }
                    result["strikes"].append(strike_info)
                
                # Cache the result
                cache_key = f"{futures_token}_{center_price}_{num_strikes}"
                self.cached_strikes[cache_key] = result
                
                logger.info(f"Found {len(result['strikes'])} nearest strikes for {futures.symbol}")
                return result
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error finding nearest strikes: {e}")
            return {}
    
    def get_all_tokens_for_streaming(self, nearest_strikes_data: Dict) -> List[str]:
        """Extract all tokens (futures + options) for streaming"""
        tokens = []
        
        # Add futures token
        if "futures" in nearest_strikes_data:
            tokens.append(nearest_strikes_data["futures"]["token"])
        
        # Add option tokens
        for strike_data in nearest_strikes_data.get("strikes", []):
            if strike_data.get("call"):
                tokens.append(strike_data["call"]["token"])
            if strike_data.get("put"):
                tokens.append(strike_data["put"]["token"])
        
        return tokens
    
    def store_strategy_tokens(self, strategy_name: str, tokens: List[str]) -> bool:
        """Store tokens for a trading strategy"""
        try:
            # In a real implementation, this would store in database or cache
            # For now, store in memory
            self.futures_tokens[strategy_name] = tokens
            logger.info(f"Stored {len(tokens)} tokens for strategy: {strategy_name}")
            return True
        except Exception as e:
            logger.error(f"Error storing strategy tokens: {e}")
            return False


# Global instance
strike_manager = StrikeManager()
