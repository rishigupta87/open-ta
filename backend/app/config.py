"""Configuration settings for the Open-TA application"""

import os
from typing import Optional

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trading:trading123@timescaledb:5432/trading_data")

# Redis Configuration  
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# AngelOne API Configuration
ANGELONE_API_KEY = os.getenv("ANGELONE_API_KEY", "")
ANGELONE_CLIENT_ID = os.getenv("ANGELONE_CLIENT_ID", "")
ANGELONE_PASSWORD = os.getenv("ANGELONE_PASSWORD", "")
ANGELONE_TOTP_SECRET = os.getenv("ANGELONE_TOTP_SECRET", "")

# AngelOne WebSocket URLs
ANGELONE_WS_URL = "wss://smartapisocket.angelone.in/smart-stream"
ANGELONE_API_BASE_URL = "https://apiconnect.angelone.in"

# Application Configuration
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Streaming Configuration
MARKET_DATA_BUFFER_SIZE = int(os.getenv("MARKET_DATA_BUFFER_SIZE", "100"))
STREAMING_INTERVAL = float(os.getenv("STREAMING_INTERVAL", "1.0"))  # seconds
REDIS_DATA_EXPIRY = int(os.getenv("REDIS_DATA_EXPIRY", "300"))  # seconds

# TimescaleDB Configuration
TIMESCALE_CHUNK_INTERVAL = os.getenv("TIMESCALE_CHUNK_INTERVAL", "1 hour")
DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "30"))

# Instrument Filtering Configuration
KEEP_EXCHANGES = ["NSE", "NFO", "MCX"]
KEEP_MCX_COMMODITIES = ["CRUDEOIL", "CRUDEOILM", "NATURALGAS", "BRCRUDEOIL"]
MAX_OPTIONS_PER_UNDERLYING = int(os.getenv("MAX_OPTIONS_PER_UNDERLYING", "5"))

# Trading Configuration
SUPPORTED_UNDERLYINGS = ["NIFTY", "BANKNIFTY", "CRUDEOIL", "NATURALGAS"]
FUTURES_LIMIT = int(os.getenv("FUTURES_LIMIT", "50"))

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
