import hashlib
import pyotp
import requests
import logzero
from typing import Optional, Dict, Any

logger = logzero.logger


class SmartAPIManager:
    """Manager for AngelOne SmartAPI integration"""
    
    def __init__(self, api_key: str, username: str, password: str, totp_token: str):
        self.api_key = api_key
        self.username = username
        self.password = password
        self.totp_token = totp_token
        self.base_url = "https://apiconnect.angelbroking.com"
        self.session = requests.Session()

        # Will be filled after login
        self.session_token = None
        self.refresh_token = None
        self.client_code = None
        self.feed_token = None  # AngelOne uses jwtToken as feedToken for SmartWS

    def authenticate(self) -> bool:
        """Authenticate with AngelOne SmartAPI"""
        try:
            totp = pyotp.TOTP(self.totp_token).now()
            password_hash = hashlib.sha256(self.password.encode()).hexdigest()

            payload = {
                "clientcode": self.username,
                "password": password_hash,
                "totp": totp
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "00:00:00:00:00:00",
                "X-PrivateKey": self.api_key
            }

            resp = self.session.post(
                f"{self.base_url}/rest/auth/angelbroking/user/v1/loginByPassword",
                json=payload,
                headers=headers
            )

            if resp.status_code != 200:
                logger.error(f"Login HTTP error: {resp.status_code}")
                return False

            data = resp.json()
            if not data.get("status"):
                logger.error(f"Login failed: {data.get('message')}")
                return False

            # Extract tokens
            self.session_token = data["data"]["jwtToken"]
            self.refresh_token = data["data"]["refreshToken"]
            self.client_code = data["data"]["clientcode"]
            # FeedToken = jwtToken (for SmartWebSocketV2)
            self.feed_token = self.session_token  

            logger.info(f"Authentication successful for user: {self.client_code}")
            return True

        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            return False    
    
    def get_feed_token(self) -> Optional[str]:
        """Retrieve feed token for WebSocket streaming"""
        if not self.session_token:
            logger.error("Cannot fetch feed token: Not authenticated")
            return None
        
        try:
            headers = {
                'Authorization': f'Bearer {self.session_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-UserType': 'USER',
                'X-SourceID': 'WEB',
                'X-PrivateKey': self.api_key
            }
            
            response = self.session.get(
                f"{self.base_url}/rest/secure/angelbroking/user/v1/getfeedToken",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    feed_token = data['data'].get('feedToken')
                    logger.info("Successfully fetched feed token")
                    return feed_token
                else:
                    logger.error(f"Feed token fetch failed: {data.get('message')}")
                    return None
            else:
                logger.error(f"Feed token request failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching feed token: {e}")
            return None
    
    def disconnect(self):
        """Disconnect session"""
        if self.session_token:
            try:
                headers = {
                    'Authorization': f'Bearer {self.session_token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-UserType': 'USER',
                    'X-SourceID': 'WEB',
                    'X-ClientLocalIP': '127.0.0.1',
                    'X-ClientPublicIP': '127.0.0.1',
                    'X-MACAddress': '00:00:00:00:00:00',
                    'X-PrivateKey': self.api_key
                }
                
                self.session.post(
                    f"{self.base_url}/rest/secure/angelbroking/user/v1/logout",
                    headers=headers
                )
                
                logger.info("Successfully disconnected")
                
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            
            finally:
                self.session_token = None
                self.refresh_token = None
                self.user_id = None
    
    def is_authenticated(self) -> bool:
        """Check if authenticated"""
        return self.session_token is not None
