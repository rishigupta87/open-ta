import pyotp
import hashlib
from SmartApi.smartConnect import SmartConnect
import logzero
from typing import Optional, Dict, Any

logger = logzero.logger

class SmartAPIManager:
    def __init__(self, api_key: str, username: str, password: str, totp_secret: str):
        self.api_key = api_key
        self.username = username
        self.password = password
        self.totp_secret = totp_secret
        self.auth_token = None
        self.feed_token = None
        self.client_code = None
        # self.client: Optional[SmartConnect] = None

    def authenticate(self) -> bool:
        try:
            # Generate TOTP and hash password
            totp = pyotp.TOTP(self.totp_secret)
            current_totp = totp.now()
            hashed_password = self.password

            # Initialize SmartConnect client
            self.client = SmartConnect(api_key=self.api_key)
            session = self.client.generateSession(
                clientCode=self.username,
                password=hashed_password,
                totp=current_totp
            )
            self.auth_token = session.get("data", {}).get("jwtToken")
            self.feed_token = self.client.getfeedToken()
            self.client_code = session.get("data", {}).get("clientCode")
            if session.get("status"):
                logger.info(f"Authentication successful for user: {self.username}")
                return True
            else:
                logger.error(f"Authentication failed: {session.get('message')}")
                return False

        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            return False

    def get_profile(self) -> Optional[Dict[str, Any]]:
        if not self.client:
            logger.error("Client not initialized or not authenticated.")
            return None

        try:
            return self.client.getProfile(refreshToken=self.client.refresh_token)
        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            return None

    def disconnect(self) -> None:
        if self.client:
            try:
                self.client.terminateSession(clientCode=self.username)
                logger.info("Session terminated successfully.")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")

    def is_authenticated(self) -> bool:
        return self.client is not None and self.client.access_token is not None
