from brokers.base_broker import BaseBroker
from neo_api_client import NeoAPI
from typing import Dict, Any, Optional

class KotakNeo(BaseBroker):
    def __init__(self, client_id: str, client_secret: str, environment: str = 'uat'):
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = NeoAPI(consumer_key=client_id, consumer_secret=client_secret, environment=environment)
        self.session_token: Optional[str] = None

    def login(self, mobilenumber: str, password: str, otp: str):
        # Initiate login
        login_response = self.client.login(mobilenumber=mobilenumber, password=password)
        if login_response.get('status') == 'success':
            # Complete 2FA
            otp_response = self.client.session_2fa(OTP=otp)
            if otp_response.get('status') == 'success':
                self.session_token = otp_response.get('data', {}).get('session_token')
                return otp_response
            else:
                raise Exception(f"2FA failed: {otp_response}")
        else:
            raise Exception(f"Login failed: {login_response}")

    def get_open_positions(self):
        if not self.session_token:
            raise Exception("Not authenticated. Please login first.")
        positions = self.client.positions()
        if positions.get("stCode") == 200:
            return positions.get("data", [])
        else:
            raise Exception(f"Failed to get positions: {positions}")

    def get_closed_positions(self):
        # Assuming closed positions can be derived from trade reports
        if not self.session_token:
            raise Exception("Not authenticated. Please login first.")
        trades = self.client.trade_report()
        if trades.get("stCode") == 200:
            return trades.get("data", [])
        else:
            raise Exception(f"Failed to get trades: {trades}")

    def get_open_orders(self):
        if not self.session_token:
            raise Exception("Not authenticated. Please login first.")
        orders = self.client.order_report()
        if orders.get("stCode") == 200:
            return orders.get("data", [])
        else:
            raise Exception(f"Failed to get orders: {orders}")

    def get_order_history(self, order_id: str):
        if not self.session_token:
            raise Exception("Not authenticated. Please login first.")
        order_history = self.client.order_history(order_id=order_id)
        if order_history.get("stCode") == 200:
            return order_history.get("data", [])
        else:
            raise Exception(f"Failed to get order history: {order_history}")

    def get_account_details(self):
        if not self.session_token:
            raise Exception("Not authenticated. Please login first.")
        account_details = self.client.limits()
        if account_details.get("stCode") == 200:
            return account_details.get("data", [])
        else:
            raise Exception(f"Failed to get account details: {account_details}")

    def get_required_margin(self, order: Dict[str, Any]):
        if not self.session_token:
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
        if not self.session_token:
            raise Exception("Not authenticated. Please login first.")
        cancel_order = self.client.cancel_order(order_id=order_id)
        if cancel_order.get("stCode") == 200:
            return cancel_order.get("data", [])
        else:
            raise Exception(f"Failed to cancel order: {cancel_order}")

    def modify_order(self, order: Dict[str, Any]):
        if not self.session_token:
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
