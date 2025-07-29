import os
import json
import redis
import pandas as pd
from kafka import KafkaConsumer
from datetime import datetime, timezone
import logzero
from logzero import logger

# ✅ Kafka config
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "stock_data")

# ✅ Redis config
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# ✅ 30 min retention
RETENTION_SECONDS = 30 * 60

# ✅ Thresholds
PRICE_CHANGE_THRESHOLD = 2.0
VOLUME_SPIKE_THRESHOLD = 1000
OI_DROP_THRESHOLD = 5.0

# ✅ Preloaded token metadata
TOKEN_LOOKUP = {}


def preload_metadata():
    """
    Load all CSV instrument metadata into TOKEN_LOOKUP for fast token→name mapping
    """
    global TOKEN_LOOKUP
    csv_files = [
        "/bridge/commodities_instruments.csv",
        "/bridge/stocks_instruments.csv",
        "/bridge/index_instruments.csv"
    ]

    total_loaded = 0

    for csv_file in csv_files:
        if not os.path.exists(csv_file):
            logger.warning(f"⚠️ Metadata file missing: {csv_file}")
            continue

        df = pd.read_csv(csv_file)
        logger.info(f"📄 Loaded {len(df)} rows from {csv_file}")

        for _, row in df.iterrows():
            TOKEN_LOOKUP[str(row["token"])] = {
                "token": str(row["token"]),
                "name": row.get("name"),
                "expiry": row.get("expiry"),
                "instrumenttype": row.get("instrumenttype"),
                "symbol": row.get("symbol"),
            }
            total_loaded += 1

    logger.info(f"✅ Preloaded metadata for {total_loaded} tokens")


def save_history(token, ltp, volume, oi):
    """
    Save each tick in Redis sorted set with timestamp as score.
    Trim anything older than 30 mins.
    """
    timestamp = int(datetime.now(timezone.utc).timestamp())
    history_key = f"history:{token}"

    tick_data = json.dumps({
        "ts": timestamp,
        "ltp": ltp,
        "volume": volume,
        "oi": oi
    })

    redis_client.zadd(history_key, {tick_data: timestamp})
    redis_client.zremrangebyscore(history_key, 0, timestamp - RETENTION_SECONDS)


def detect_signals(token):
    """
    Detect signals using last 5 min history
    """
    now = int(datetime.now(timezone.utc).timestamp())
    lookback_5min = now - 5 * 60
    history_key = f"history:{token}"

    recent_ticks = redis_client.zrangebyscore(history_key, lookback_5min, now)
    if len(recent_ticks) < 2:
        return

    parsed = [json.loads(x) for x in recent_ticks]
    prices = [p["ltp"] for p in parsed]
    volumes = [p["volume"] for p in parsed if p["volume"] is not None]
    oi_vals = [p["oi"] for p in parsed if p["oi"] is not None]

    if not prices or not volumes:
        return

    price_change_pct = ((prices[-1] - prices[0]) / prices[0]) * 100
    volume_change = volumes[-1] - volumes[0] if len(volumes) > 1 else 0
    oi_change_pct = 0

    if len(oi_vals) > 1 and oi_vals[0] > 0:
        oi_change_pct = ((oi_vals[-1] - oi_vals[0]) / oi_vals[0]) * 100

    signal = None
    if price_change_pct > PRICE_CHANGE_THRESHOLD and volume_change > VOLUME_SPIKE_THRESHOLD:
        signal = "BUY breakout"
    elif price_change_pct < -PRICE_CHANGE_THRESHOLD and oi_change_pct < -OI_DROP_THRESHOLD:
        signal = "SELL - weak OI"

    if signal:
        redis_client.set(f"signal:{token}", json.dumps({
            "token": token,
            "signal": signal,
            "price_change_pct": round(price_change_pct, 2),
            "volume_change": volume_change,
            "oi_change_pct": round(oi_change_pct, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
        logger.warning(f"🚨 SIGNAL [{token}] → {signal} "
                       f"(Price {price_change_pct:.2f}% Vol Δ{volume_change} OI Δ{oi_change_pct:.2f}%)")


def process_message(data: dict):
    """
    Process incoming Kafka tick
    """
    token = data.get("token")
    ltp = data.get("last_traded_price")
    volume = data.get("volume_trade_for_the_day")
    oi = data.get("open_interest")

    if not token:
        logger.error("❌ Received Kafka tick with no token")
        return

    # ✅ Normalize price (Angel sends paise sometimes)
    if isinstance(ltp, (int, float)):
        ltp = round(ltp / 100, 2)
        data["last_traded_price"] = ltp

    logger.debug(f"📥 Tick [{token}] → LTP:{ltp} Vol:{volume} OI:{oi}")

    # ✅ Save latest snapshot
    redis_client.set(f"stock:{token}", json.dumps(data))

    # ✅ Save metadata only once
    meta_key = f"stock:meta:{token}"
    if not redis_client.exists(meta_key):
        meta_info = TOKEN_LOOKUP.get(str(token))
        if meta_info:
            redis_client.set(meta_key, json.dumps(meta_info))
            logger.info(f"ℹ️ Saved metadata for token {token} → "
                        f"{meta_info['name']} (expiry {meta_info['expiry']})")
        else:
            logger.warning(f"⚠️ No metadata found for token {token}")

    # ✅ Save tick history
    save_history(token, ltp, volume, oi)

    # ✅ Detect signals
    detect_signals(token)


def consume_kafka():
    """
    Kafka consumer reading market data
    """
    logger.info(f"✅ Connecting to Kafka @ {KAFKA_BOOTSTRAP_SERVERS} ...")

    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="stock_consumer_group"
    )

    logger.info(f"✅ Listening on Kafka topic: {TOPIC}")

    for message in consumer:
        try:
            data = message.value
            process_message(data)
        except Exception as e:
            logger.exception(f"❌ Error processing Kafka message: {e}")


if __name__ == "__main__":
    logger.info("🚀 Starting Kafka Consumer with metadata preload...")
    preload_metadata()
    consume_kafka()
