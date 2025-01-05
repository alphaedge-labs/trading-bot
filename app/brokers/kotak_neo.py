from brokers.base_broker import BaseBroker
from neo_api_client import NeoAPI
from typing import Dict, Any, Optional
from utils.logging import logger
from database.redis import redis_client
from constants.redis import HashSets
from utils.id_generator import generate_id
class KotakNeo(BaseBroker):
    def __init__(self, client_id: str, client_secret: str, environment: str = 'prod', access_token: str = None, neo_fin_key: str = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = NeoAPI(consumer_key=client_id, consumer_secret=client_secret, environment=environment, access_token=None, neo_fin_key=None)
        self.session_token: Optional[str] = None
        self.authenticated: bool = False

    def login(self, mobilenumber: str, password: str):
        # Initiate login
        logger.info(f"Logging in to Kotak Neo with mobilenumber: {mobilenumber} and password: {password}")
        login_response = self.client.login(mobilenumber=mobilenumber, password=password)
        
        if login_response.get('data', {}).get('token'):
            self.session_token = login_response.get('data', {}).get('token')
            return login_response
        else:
            raise Exception(f"Login failed: {login_response}")
    
    def authenticate(self, otp: str):
        if not self.session_token:
            raise Exception("Not authenticated. Please login first.")
        otp_response = self.client.session_2fa(OTP=otp)
        if otp_response.get('data', {}).get('token'):
            self.session_token = otp_response.get('data', {}).get('token')
            self.authenticated = True
            
            # Set up event handlers
            self.client.on_message = self.on_message
            self.client.on_error = self.on_error
            self.client.on_close = self.on_close
            self.client.on_open = self.on_open

            return otp_response
        else:
            raise Exception(f"2FA failed: {otp_response}")

    def on_message(self, message: str):
        # called when a message is received from the websocket
        logger.info(f"Received message: {message}")

    def on_error(self, error: str):
        # called when any error or exception occurs in code or websocket
        logger.error(f"Error: {error}")

    def on_close(self):
        # called when websocket connection is closed
        logger.info("Websocket connection closed")

    def on_open(self):
        # called when websocket successfully connects
        logger.info("Websocket connection opened")

    def get_open_positions(self):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        positions = self.client.positions()
        if positions.get("stCode") == 200:
            return positions.get("data", [])
        else:
            raise Exception(f"Failed to get positions: {positions}")

    def get_closed_positions(self):
        # Assuming closed positions can be derived from trade reports
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        trades = self.client.trade_report()
        if trades.get("stCode") == 200:
            return trades.get("data", [])
        else:
            raise Exception(f"Failed to get trades: {trades}")

    def get_open_orders(self):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        orders = self.client.order_report()
        if orders.get("stCode") == 200:
            return orders.get("data", [])
        else:
            raise Exception(f"Failed to get orders: {orders}")

    def get_order_history(self, order_id: str):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        order_history = self.client.order_history(order_id=order_id)
        if order_history.get("stCode") == 200:
            return order_history.get("data", [])
        else:
            raise Exception(f"Failed to get order history: {order_history}")

    def get_account_details(self):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        account_details = self.client.limits()
        if account_details.get("stCode") == 200:
            return account_details.get("data", [])
        else:
            raise Exception(f"Failed to get account details: {account_details}")

    def get_required_margin(self, order: Dict[str, Any]):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        margin_required = self.client.margin_required(
            exchange_segment=order.get('exchange_segment', ''),
            price=order.get('price', ''),
            order_type=order.get('order_type', ''),
            product=order.get('product', ''),
            quantity=order.get('quantity', ''),
            instrument_token=order.get('instrument_token', ''),
            transaction_type=order.get('transaction_type', '')
        )
        if margin_required.get("stCode") == 200:
            return margin_required.get("data", [])
        else:
            raise Exception(f"Failed to get margin required: {margin_required}")
        
    def cancel_order(self, order_id: str):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        cancel_order = self.client.cancel_order(order_id=order_id)
        if cancel_order.get("stCode") == 200:
            return cancel_order.get("data", [])
        else:
            raise Exception(f"Failed to cancel order: {cancel_order}")

    def modify_order(self, order: Dict[str, Any]):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        modify_order = self.client.modify_order(
            instrument_token=order.get('instrument_token', ''),
            exchange_segment=order.get('exchange_segment', ''),
            product=order.get('product', ''),
            price=order.get('price', ''),
            order_type=order.get('order_type', ''),
            quantity=order.get('quantity', ''),
            validity=order.get('validity', ''),
            trading_symbol=order.get('trading_symbol', ''),
            transaction_type=order.get('transaction_type', ''),
            order_id=order.get('order_id', ''),
            amo=order.get('amo', '')
        )
        if modify_order.get("stCode") == 200:
            return modify_order.get("data", [])
        else:
            raise Exception(f"Failed to modify order: {modify_order}")

    async def form_order(self, data: Dict[str, Any], is_exit: bool):
        key = redis_client._generate_key(data)
        mappings = await redis_client.get_hash_by_key(HashSets.INSTRUMENTS.value, key)
        if not mappings:
            raise Exception(f"Instrument not found for key: {key}")
        
        kotak_mappings = mappings.get('kotak_neo', {})
        if not kotak_mappings:
            raise Exception(f"Kotak Neo mappings not found for key: {key}")

        data['order_id'] = f'ord_{generate_id()}'
        data['exchange_segment'] = kotak_mappings.get('exchange_segment', '')
        data['trading_symbol'] = kotak_mappings.get('trading_symbol', '')

        return data
    
    async def place_order(self, order: Dict[str, Any]):
        self.client.place_order(
            # values from kotak_mappings
            exchange_segment=order.get('exchange_segment', ''), 
            trading_symbol=order.get('trading_symbol', ''),
            # values from order
            product=order.get('product', ''),
            order_type=order.get('order_type', ''), 
            quantity=order.get('quantity', ''), 
            validity=order.get('validity', ''), 
            transaction_type=order.get('transaction_type', ''), 
            # optional
            price=order.get('price', None), 
            amo=order.get('amo', None), 
            disclosed_quantity=order.get('disclosed_quantity', None), 
            market_protection=order.get('market_protection', None), 
            pf=order.get('pf', None),
            trigger_price=order.get('trigger_price', None), 
            tag=order.get('tag', None)
        )

        return order