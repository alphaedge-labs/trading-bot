from typing import Dict, Any
from datetime import datetime
from kiteconnect import KiteConnect

from brokers.base_broker import BaseBroker
from constants.brokers import Broker
from utils.logging import logger
from utils.id_generator import generate_id
from database.redis import redis_client
from constants.redis import HashSets
from constants.orders import Exchange, Validity, Variety, Product, OrderType

class ZerodhaKite(BaseBroker):
    def __init__(self, client_id: str, client_secret: str, access_token: str):
        if not client_id or not client_secret:
            logger.error("client_id and client_secret are required")
            raise ValueError("client_id and client_secret are required")
            
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.kite = None
        self.authenticated = False
        self.redis_client = redis_client
        logger.success(f"ZerodhaKite initialized for client: {client_id}")

    async def login(self):
        try:
            self.kite = KiteConnect(api_key=self.client_id, access_token=self.access_token)

            profile = self.kite.profile()
            if profile.get("user_id"):
                self.authenticated = True
                await self.redis_client._connect()

                return {"status": "success", "message": "Logged in successfully"}
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise

    async def get_zerodha_instrument(self, signal_data: Dict[str, Any]):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        instrument_identifier = self.redis_client._generate_key(signal_data)

        # logger.info(f"Instrument identifier: {instrument_identifier}")

        instrument = await self.redis_client.get_hash(HashSets.INSTRUMENTS.value, instrument_identifier)

        # logger.info(f"Instrument in redis: {instrument}")

        # {"zerodha": {"instrument_token": "12107266", "exchange_token": "47294", "trading_symbol": "NIFTY24D1922700CE", "instrument_type": "CE", "exchange": "NFO", "segment": "NFO-OPT", "lot_size": "25", "tick_size": "0.05"}}

        if not instrument:
            raise Exception("Instrument not found in Redis")
        
        zerodha_instrument = instrument.get("zerodha")
        if not zerodha_instrument:
            raise Exception("Zerodha instrument not found in Redis")
        
        zerodha_instrument["tick_size"] = float(zerodha_instrument["tick_size"])
        zerodha_instrument["lot_size"] = int(zerodha_instrument["lot_size"])
        zerodha_instrument["instrument_token"] = int(zerodha_instrument["instrument_token"])
        zerodha_instrument["exchange_token"] = int(zerodha_instrument["exchange_token"])

        return zerodha_instrument

    def get_open_positions(self):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        return self.kite.positions()["net"]

    def get_closed_positions(self):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        return self.kite.positions()["day"]

    def get_open_orders(self):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        return self.kite.orders()

    def get_order_history(self):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        return self.kite.orders()

    def get_account_details(self):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        return self.kite.margins()

    async def get_required_margin(self, order: Dict[str, Any]):
        zerodha_instrument = await self.get_zerodha_instrument(order)

        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        
        params = [{
            "tradingsymbol": zerodha_instrument.get("trading_symbol", ""),
            "variety": "regular",
            "exchange": order.get("exchange", "NSE"),
            "transaction_type": order.get("transaction_type", ""),
            "quantity": order.get("quantity", 0),
            "product": order.get("product", "MIS"),
            "order_type": order.get("order_type", "MARKET"),
            "price": order.get("price", 0)
        }]
        
        margins = self.kite.order_margins(params)

        if not margins:
            logger.error("No margins found")
            return 0
        
        return margins[0].get("total", 999999999999) # Absurdly big number so trade can be placed


    def cancel_order(self, order_id: str):
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")
        return self.kite.cancel_order(variety="regular", order_id=order_id)

    async def form_order(self, data: Dict[str, Any], is_exit: bool=False):
        """Forms an order for Zerodha Kite"""
        zerodha_instrument = await self.get_zerodha_instrument(data)

        order = {
            "tradingsymbol": zerodha_instrument.get("trading_symbol"),
            "quantity": data["quantity"],
            "product": data.get("product", Product.MIS.value),
            "order_type": data.get("order_type", OrderType.MARKET.value),
            "price": data.get("entry_price" if not is_exit else 0),
            "trigger_price": data.get("stop_loss"),
            "disclosed_quantity": 0,
            "validity": data.get("validity", Validity.DAY.value),
            "variety": data.get("variety", Variety.REGULAR.value),
            "exchange": data.get("exchange", Exchange.NFO.value),
            "user_id": self.client_id,
            "timestamp": datetime.now().isoformat()
        }

        if data.get("validity") == Validity.TTL.value:
            order["validity_ttl"] = data.get("validity_ttl", 2)

        transaction_type = data.get("transaction_type", "BUY")
        order["transaction_type"] = "BUY" if transaction_type == "BUY" else "SELL"
        order["is_exit"] = True if is_exit else False

        if is_exit:
            order["transaction_type"] = "SELL" if transaction_type == "BUY" else "BUY"

        return order

    async def place_order(self, order: Dict[str, Any]):
        """Places an order with Zerodha Kite"""
        if not self.authenticated:
            raise Exception("Not authenticated. Please login first.")

        # logger.info(f"Order: {order}")

        try:
            order_id = self.kite.place_order(
                variety="regular",
                exchange=order["exchange"],
                tradingsymbol=order["tradingsymbol"],
                transaction_type=order["transaction_type"],
                quantity=order["quantity"],
                product=order["product"],
                validity=order.get("validity", "DAY"),
                validity_ttl=order.get("validity_ttl", None),
                order_type=order["order_type"] if not order["is_exit"] else "MARKET",
                price=round(order.get("price"), 2) if not order["is_exit"] else 0,
                disclosed_quantity=order.get("disclosed_quantity", 0),
                tag=order.get("guid")
            )

            if not order_id:
                raise Exception("Order placement failed")

            return order_id
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise