import os
import pandas as pd
from datetime import datetime
from smart_api_manager import SmartAPIManager
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from kafka_producer import send_to_kafka
import logzero
from logzero import logger

CSV_PATH = "/app/commodities_instruments.csv"

class TokenManager:
    def __init__(self, csv_path=CSV_PATH):
        self.df = pd.read_csv(csv_path, parse_dates=["expiry"])
        logger.info(f"📄 Loaded {len(self.df)} rows from {csv_path}")

    def get_nearest_futures(self):
        """Pick nearest FUTCOM for each symbol"""
        fut_df = self.df[self.df["instrumenttype"] == "FUTCOM"].copy()
        fut_df = fut_df.sort_values(["name", "expiry"])
        return fut_df.groupby("name").head(1).reset_index(drop=True)

    def get_nearest_option_tokens(self, name, expiry, fut_ltp, strikes_per_side=1):
        """Find ATM ± strikes_per_side CE & PE for given expiry"""
        opt_df = self.df[(self.df["name"].str.upper() == name.upper()) &
                         (self.df["instrumenttype"] == "OPTFUT") &
                         (self.df["expiry"] == expiry)]

        if opt_df.empty:
            logger.warning(f"⚠️ No options for {name} {expiry}")
            return []

        opt_df["strike"] = pd.to_numeric(opt_df["strike"], errors="coerce")

        # ATM strike closest to FUT LTP
        atm_strike = opt_df.iloc[(opt_df["strike"] - fut_ltp).abs().argsort()[:1]]["strike"].iloc[0]

        sorted_df = opt_df.iloc[(opt_df["strike"] - atm_strike).abs().argsort()]
        nearest_opts = sorted_df.head((strikes_per_side * 2) + 2)

        logger.info(f"🎯 ATM {atm_strike} → selected {len(nearest_opts)} option strikes")
        return nearest_opts["token"].astype(str).tolist()

token_manager = TokenManager()

class KafkaBridgeSmartWS(SmartWebSocketV2):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initially subscribe only nearest FUT tokens
        nearest_futs = token_manager.get_nearest_futures()
        self.future_tokens = nearest_futs["token"].astype(str).tolist()
        self.future_map = {
            row["token"]: {
                "name": row["name"],
                "expiry": row["expiry"]
            }
            for _, row in nearest_futs.iterrows()
        }

        logger.info(f"📡 Initial FUT tokens: {self.future_tokens}")
        self.subscribed_options = set()   # track options already subscribed

    def on_data(self, wsapp, data):
        # ✅ Always push to Kafka
        if data.get("subscription_mode_val") == "SNAP_QUOTE":
            send_to_kafka("stock_data", data)

        token = data.get("token")
        ltp = data.get("last_traded_price")

        # ✅ First FUT tick → derive ATM options
        if token in self.future_map and ltp:
            fut_ltp = round(ltp / 100, 2)  # normalize
            meta = self.future_map[token]
            name = meta["name"]
            expiry = meta["expiry"]

            logger.info(f"📥 FUT LTP for {name} → {fut_ltp}")

            option_tokens = token_manager.get_nearest_option_tokens(name, expiry, fut_ltp, strikes_per_side=1)

            # Avoid duplicate subscriptions
            new_tokens = [t for t in option_tokens if t not in self.subscribed_options]
            if new_tokens:
                logger.info(f"🆕 Subscribing ATM options for {name}: {new_tokens}")
                self.dynamic_subscribe(new_tokens)
                self.subscribed_options.update(new_tokens)

    def on_open(self, wsapp):
        logger.info("[INFO] WebSocket Opened - Subscribing FUT first…")
        if not self.future_tokens:
            logger.warning("❌ No futures tokens to subscribe")
            return

        self.subscribe(
            correlation_id="fut-init",
            mode=self.SNAP_QUOTE,
            token_list=[{"exchangeType": self.MCX_FO, "tokens": self.future_tokens}]
        )

    def dynamic_subscribe(self, tokens):
        self.subscribe(
            correlation_id="options",
            mode=self.SNAP_QUOTE,
            token_list=[{"exchangeType": self.MCX_FO, "tokens": tokens}]
        )

    def on_error(self, type, message):
        logger.error(f"[WebSocket Error] {type}: {message}")

    def on_close(self, wsapp):
        logger.warning("[INFO] WebSocket closed")

if __name__ == "__main__":
    api_key = os.getenv("API_KEY")
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    totp_secret = os.getenv("TOTP_SECRET")

    manager = SmartAPIManager(api_key, username, password, totp_secret)

    if not manager.authenticate():
        logger.error("Login failed. Exiting.")
        exit(1)

    jwt_token   = manager.auth_token
    feed_token  = manager.feed_token
    client_code = manager.username
    logger.info(f"✅ Authenticated → JWT:{jwt_token[:10]}… FEED:{feed_token[:6]}…")

    bridge = KafkaBridgeSmartWS(
        auth_token=jwt_token,
        api_key=api_key,
        client_code=client_code,
        feed_token=feed_token
    )
    bridge.connect()
