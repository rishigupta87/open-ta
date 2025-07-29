"""OI-based signal generation engine for real-time options trading"""

import asyncio
import pytz
from datetime import datetime, time, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, desc
import logzero

from ..db.models import MarketData, OISignal, OIAnalytics, TradingInstrument
from ..db.database import SessionLocal
from ..config import SUPPORTED_UNDERLYINGS

logger = logzero.logger

# India timezone
IST = pytz.timezone('Asia/Kolkata')

class OISignalEngine:
    """Real-time OI signal generation and analysis engine"""
    
    def __init__(self):
        self.is_running = False
        self.signal_history: Dict[str, Dict] = {}
        self.current_signals: List[Dict] = []
        
        # Trading hours configuration
        self.trading_hours = {
            'MCX': {
                'start': time(9, 0),    # 9:00 AM
                'end': time(23, 30),    # 11:30 PM
            },
            'NSE': {
                'start': time(9, 20),   # 9:20 AM
                'end': time(15, 30),    # 3:30 PM
            },
            'NFO': {
                'start': time(9, 20),   # 9:20 AM
                'end': time(15, 30),    # 3:30 PM
            }
        }
        
        # Signal thresholds
        self.thresholds = {
            'min_iv': 15.0,              # Minimum IV percentage
            'strong_oi_change': 20.0,    # Strong signal OI change %
            'medium_oi_change': 10.0,    # Medium signal OI change %
            'min_oi_absolute': 1000,     # Minimum absolute OI change
            'analysis_window': 300,      # 5 minutes in seconds
        }
    
    def is_market_open(self, exchange: str) -> bool:
        """Check if market is currently open for given exchange"""
        try:
            now_ist = datetime.now(IST)
            current_time = now_ist.time()
            current_weekday = now_ist.weekday()  # Monday=0, Sunday=6
            
            # Check if it's a trading day (Monday=0 to Friday=4)
            if current_weekday > 4:  # Saturday=5, Sunday=6
                return False
            
            hours = self.trading_hours.get(exchange.upper())
            
            if not hours:
                return False
                
            return hours['start'] <= current_time <= hours['end']
            
        except Exception as e:
            logger.error(f"Error checking market hours for {exchange}: {e}")
            return False
    
    def get_active_exchanges(self) -> List[str]:
        """Get list of currently active exchanges"""
        active = []
        for exchange in ['MCX', 'NSE', 'NFO']:
            if self.is_market_open(exchange):
                active.append(exchange)
        return active
    
    def get_detailed_market_status(self) -> Dict[str, Any]:
        """Get detailed market status including weekday information"""
        try:
            now_ist = datetime.now(IST)
            current_time = now_ist.time()
            current_weekday = now_ist.weekday()  # Monday=0, Sunday=6
            
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            current_day_name = weekday_names[current_weekday]
            
            is_trading_day = current_weekday <= 4  # Monday to Friday
            active_exchanges = self.get_active_exchanges()
            
            # Determine market status reason
            if not is_trading_day:
                status_reason = f"Weekend - Markets closed on {current_day_name}"
            elif not active_exchanges:
                status_reason = "Outside trading hours"
            else:
                status_reason = f"{len(active_exchanges)} exchange(s) active"
            
            # Next trading day info
            if current_weekday == 4:  # Friday
                next_trading_day = "Monday"
                days_until_next = 3
            elif current_weekday == 5:  # Saturday  
                next_trading_day = "Monday"
                days_until_next = 2
            elif current_weekday == 6:  # Sunday
                next_trading_day = "Monday" 
                days_until_next = 1
            else:  # Monday to Thursday
                next_trading_day = weekday_names[current_weekday + 1]
                days_until_next = 1
            
            return {
                'current_time_ist': now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
                'current_day': current_day_name,
                'is_trading_day': is_trading_day,
                'is_any_market_open': len(active_exchanges) > 0,
                'active_exchanges': active_exchanges,
                'status_reason': status_reason,
                'next_trading_day': next_trading_day,
                'days_until_next_trading': days_until_next if not is_trading_day else 0,
                'trading_hours': {
                    'MCX': '9:00 AM - 11:30 PM IST (Mon-Fri)',
                    'NSE': '9:20 AM - 3:30 PM IST (Mon-Fri)', 
                    'NFO': '9:20 AM - 3:30 PM IST (Mon-Fri)'
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting detailed market status: {e}")
            return {
                'current_time_ist': datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                'current_day': 'Unknown',
                'is_trading_day': False,
                'is_any_market_open': False,
                'active_exchanges': [],
                'status_reason': f"Error: {str(e)}",
                'next_trading_day': 'Unknown',
                'days_until_next_trading': 0,
                'trading_hours': {}
            }
    
    async def get_latest_oi_data(self, db: Session, token: str, minutes: int = 5) -> List[Dict]:
        """Get latest OI data for a token within specified minutes"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
            
            query = text("""
                SELECT 
                    timestamp,
                    token,
                    symbol,
                    ltp,
                    oi,
                    oi_change,
                    exchange,
                    instrument_type
                FROM market_data 
                WHERE token = :token 
                AND timestamp >= :cutoff_time
                ORDER BY timestamp DESC
                LIMIT 50
            """)
            
            result = db.execute(query, {
                'token': token,
                'cutoff_time': cutoff_time
            })
            
            return [dict(row) for row in result]
            
        except Exception as e:
            logger.error(f"Error getting OI data for token {token}: {e}")
            return []
    
    def calculate_oi_change_percent(self, current_oi: int, previous_oi: int) -> float:
        """Calculate OI change percentage"""
        if previous_oi == 0:
            return 0.0
        return ((current_oi - previous_oi) / previous_oi) * 100
    
    def calculate_implied_volatility(self, current_price: float, strike: float, option_type: str) -> float:
        """Calculate implied volatility (simplified Black-Scholes approximation)"""
        try:
            # Simplified IV calculation - in production, use proper BS model
            if option_type in ['CE', 'CALL']:
                if current_price > strike:
                    # ITM call
                    iv = min(((current_price - strike) / strike) * 100, 100)
                else:
                    # OTM call
                    iv = max((strike - current_price) / strike * 50, 5)
            elif option_type in ['PE', 'PUT']:
                if current_price < strike:
                    # ITM put
                    iv = min(((strike - current_price) / strike) * 100, 100)
                else:
                    # OTM put
                    iv = max((current_price - strike) / strike * 50, 5)
            else:
                iv = 15.0  # Default for futures
                
            return max(min(iv, 200), 0)  # Cap between 0-200%
            
        except Exception as e:
            logger.error(f"Error calculating IV: {e}")
            return 15.0
    
    def determine_signal_strength(self, oi_change_percent: float, iv: float, oi_change_abs: int) -> str:
        """Determine signal strength based on OI change and IV"""
        if (abs(oi_change_percent) >= self.thresholds['strong_oi_change'] and 
            iv >= self.thresholds['min_iv'] and 
            abs(oi_change_abs) >= self.thresholds['min_oi_absolute']):
            return 'STRONG'
        elif (abs(oi_change_percent) >= self.thresholds['medium_oi_change'] and 
              iv >= self.thresholds['min_iv']):
            return 'MEDIUM'
        else:
            return 'WEAK'
    
    def determine_signal_type(self, oi_change: int, option_type: str) -> str:
        """Determine signal type based on OI change and option type"""
        if option_type in ['CE', 'CALL']:
            if oi_change > 0:
                return 'BULLISH'  # Call buying
            else:
                return 'BEARISH'  # Call selling
        elif option_type in ['PE', 'PUT']:
            if oi_change > 0:
                return 'BEARISH'  # Put buying
            else:
                return 'BULLISH'  # Put selling
        else:  # Futures
            if oi_change > 0:
                return 'BULLISH'  # Long buildup
            else:
                return 'BEARISH'  # Short covering
    
    async def analyze_token_oi(self, db: Session, token: str) -> Optional[Dict]:
        """Analyze OI data for a single token and generate signals"""
        try:
            # Get latest OI data
            oi_data = await self.get_latest_oi_data(db, token, 5)
            
            if len(oi_data) < 2:
                return None
                
            current = oi_data[0]
            previous = oi_data[1]
            
            # Calculate OI changes
            current_oi = current.get('oi', 0)
            previous_oi = previous.get('oi', 0)
            oi_change = current_oi - previous_oi
            oi_change_percent = self.calculate_oi_change_percent(current_oi, previous_oi)
            
            # Get instrument details
            instrument = db.query(TradingInstrument).filter(
                TradingInstrument.token == token
            ).first()
            
            if not instrument:
                return None
            
            # Calculate IV
            current_price = current.get('ltp', 0)
            option_type = 'FUTURE'
            if 'CE' in instrument.symbol:
                option_type = 'CE'
            elif 'PE' in instrument.symbol:
                option_type = 'PE'
                
            iv = self.calculate_implied_volatility(
                current_price, 
                instrument.strike or current_price, 
                option_type
            )
            
            # Check if signal meets minimum criteria
            if iv < self.thresholds['min_iv']:
                return None
                
            # Determine signal characteristics
            signal_strength = self.determine_signal_strength(oi_change_percent, iv, abs(oi_change))
            signal_type = self.determine_signal_type(oi_change, option_type)
            
            signal_data = {
                'timestamp': datetime.utcnow(),
                'token': token,
                'symbol': instrument.symbol,
                'current_oi': current_oi,
                'previous_oi': previous_oi,
                'oi_change': oi_change,
                'oi_change_percent': oi_change_percent,
                'current_price': current_price,
                'implied_volatility': iv,
                'signal_strength': signal_strength,
                'signal_type': signal_type,
                'exchange': instrument.exch_seg,
                'instrument_type': instrument.instrumenttype,
                'underlying': instrument.name,
                'strike_price': instrument.strike,
                'option_type': option_type,
                'analysis_window': '5m'
            }
            
            return signal_data
            
        except Exception as e:
            logger.error(f"Error analyzing token {token}: {e}")
            return None
    
    async def generate_signals(self, db: Session) -> List[Dict]:
        """Generate signals for all active tokens"""
        try:
            signals = []
            
            # Get streaming tokens for current active exchanges
            active_exchanges = self.get_active_exchanges()
            if not active_exchanges:
                logger.info("No markets currently open")
                return signals
            
            # Get tokens for active exchanges
            from ..db.operations import get_streaming_tokens_for_trading
            tokens_dict = get_streaming_tokens_for_trading(db)
            
            all_tokens = []
            all_tokens.extend(tokens_dict.get('futures', []))
            all_tokens.extend(tokens_dict.get('options_ce', []))
            all_tokens.extend(tokens_dict.get('options_pe', []))
            
            logger.info(f"Analyzing {len(all_tokens)} tokens for OI signals")
            
            # Analyze each token
            for token in all_tokens:
                signal = await self.analyze_token_oi(db, token)
                if signal:
                    signals.append(signal)
            
            # Filter and sort signals
            valid_signals = [s for s in signals if s['signal_strength'] in ['STRONG', 'MEDIUM']]
            valid_signals.sort(key=lambda x: abs(x['oi_change_percent']), reverse=True)
            
            logger.info(f"Generated {len(valid_signals)} valid signals")
            return valid_signals
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return []
    
    async def store_signals(self, db: Session, signals: List[Dict]) -> int:
        """Store generated signals in database"""
        try:
            stored_count = 0
            
            for signal_data in signals:
                signal = OISignal(**signal_data)
                db.add(signal)
                stored_count += 1
            
            db.commit()
            logger.info(f"Stored {stored_count} signals to database")
            return stored_count
            
        except Exception as e:
            logger.error(f"Error storing signals: {e}")
            db.rollback()
            return 0
    
    async def calculate_market_analytics(self, db: Session) -> Dict:
        """Calculate aggregated market analytics"""
        try:
            analytics = {}
            
            for underlying in SUPPORTED_UNDERLYINGS:
                # Get recent signals for this underlying
                recent_signals = db.query(OISignal).filter(
                    and_(
                        OISignal.underlying == underlying,
                        OISignal.timestamp >= datetime.utcnow() - timedelta(minutes=5)
                    )
                ).all()
                
                if not recent_signals:
                    continue
                
                # Calculate analytics
                call_signals = [s for s in recent_signals if s.option_type == 'CE']
                put_signals = [s for s in recent_signals if s.option_type == 'PE']
                
                total_call_oi_change = sum(s.oi_change for s in call_signals)
                total_put_oi_change = sum(s.oi_change for s in put_signals)
                
                # Find max changes
                max_call_signal = max(call_signals, key=lambda x: abs(x.oi_change), default=None)
                max_put_signal = max(put_signals, key=lambda x: abs(x.oi_change), default=None)
                
                # Calculate sentiment
                bullish_signals = len([s for s in recent_signals if s.signal_type == 'BULLISH'])
                bearish_signals = len([s for s in recent_signals if s.signal_type == 'BEARISH'])
                
                if bullish_signals > bearish_signals:
                    sentiment = 'BULLISH'
                    sentiment_score = (bullish_signals - bearish_signals) / len(recent_signals)
                elif bearish_signals > bullish_signals:
                    sentiment = 'BEARISH'
                    sentiment_score = (bearish_signals - bullish_signals) / len(recent_signals) * -1
                else:
                    sentiment = 'NEUTRAL'
                    sentiment_score = 0.0
                
                analytics[underlying] = {
                    'timestamp': datetime.utcnow(),
                    'underlying': underlying,
                    'total_oi_change': total_call_oi_change + total_put_oi_change,
                    'call_oi_change': total_call_oi_change,
                    'put_oi_change': total_put_oi_change,
                    'max_call_oi_change': max_call_signal.oi_change if max_call_signal else 0,
                    'max_put_oi_change': max_put_signal.oi_change if max_put_signal else 0,
                    'max_call_oi_token': max_call_signal.token if max_call_signal else '',
                    'max_put_oi_token': max_put_signal.token if max_put_signal else '',
                    'avg_iv': sum(s.implied_volatility for s in recent_signals) / len(recent_signals),
                    'max_iv': max(s.implied_volatility for s in recent_signals),
                    'high_iv_count': len([s for s in recent_signals if s.implied_volatility > 15]),
                    'pcr_oi': abs(total_put_oi_change / total_call_oi_change) if total_call_oi_change != 0 else 0,
                    'market_sentiment': sentiment,
                    'sentiment_score': sentiment_score,
                    'exchange': recent_signals[0].exchange,
                    'session_type': 'REGULAR'
                }
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error calculating market analytics: {e}")
            return {}
    
    async def store_analytics(self, db: Session, analytics: Dict) -> int:
        """Store market analytics in database"""
        try:
            stored_count = 0
            
            for underlying, data in analytics.items():
                analytic = OIAnalytics(**data)
                db.add(analytic)
                stored_count += 1
            
            db.commit()
            logger.info(f"Stored {stored_count} analytics records")
            return stored_count
            
        except Exception as e:
            logger.error(f"Error storing analytics: {e}")
            db.rollback()
            return 0
    
    async def run_signal_analysis(self):
        """Main signal analysis loop"""
        self.is_running = True
        logger.info("Starting OI signal analysis engine")
        
        while self.is_running:
            try:
                db = SessionLocal()
                try:
                    # Check if any markets are open
                    active_exchanges = self.get_active_exchanges()
                    if not active_exchanges:
                        logger.info("No markets open, sleeping...")
                        await asyncio.sleep(60)  # Check every minute when markets are closed
                        continue
                    
                    logger.info(f"Active exchanges: {active_exchanges}")
                    
                    # Generate signals
                    signals = await self.generate_signals(db)
                    
                    if signals:
                        # Store signals
                        await self.store_signals(db, signals)
                        
                        # Update current signals for real-time access
                        self.current_signals = signals[:10]  # Keep top 10 signals
                        
                        # Calculate and store analytics
                        analytics = await self.calculate_market_analytics(db)
                        if analytics:
                            await self.store_analytics(db, analytics)
                    
                    # Wait for next analysis cycle (5 minutes)
                    await asyncio.sleep(300)
                    
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"Error in signal analysis loop: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    def stop_analysis(self):
        """Stop the signal analysis engine"""
        self.is_running = False
        logger.info("Stopping OI signal analysis engine")
    
    def get_current_signals(self, limit: int = 10) -> List[Dict]:
        """Get current active signals"""
        return self.current_signals[:limit]


# Global signal engine instance
oi_signal_engine = OISignalEngine()
