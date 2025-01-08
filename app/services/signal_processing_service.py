import json
import asyncio
from typing import Dict, List, Tuple
from loguru import logger
from datetime import datetime

from models.user import User
from database.redis import redis_client
from database.manager import DatabaseManager

from services.trading_service import TradingService
from services.user_service import UserService
from services.order_service import OrderService

from constants.redis import HashSets
from constants.brokers import Broker
from constants.collections import Collections
from constants.orders import OrderType, Validity, Variety, TransactionType, OrderStatus, Exchange, Product

from utils.id_generator import generate_id
from utils.datetime import is_within_trading_hours, get_ist_time

MAX_POSITION_SIZE = 900

class SignalProcessingService:
    def __init__(self, user_service: UserService, trading_service: TradingService, order_service: OrderService):
        self.user_service = user_service
        # Create a dedicated pubsub connection
        self.redis_client = redis_client.get_new_connection()
        self.channels = ["signals"]
        self.running = False
        self.trading_service = trading_service
        self.order_service = order_service
        self.db_manager = DatabaseManager()
        self.db = None

    async def start(self):
        """Start the signal processing service"""
        if self.running:
            logger.warning("Signal processing service is already running")
            return

        # Ensure Redis connection is established
        try:
            # Initialize Redis connection
            await self.redis_client._connect()
            self.db = await self.db_manager.get_db()
            await asyncio.gather(
                self.trading_service.start_listening(),
                self.order_service.start(),
                self.start_listening(),
                self._check_trading_hours()
            )
        except Exception as e:
            logger.error(f"Error starting signal processing service: {e}")
            raise

    async def _check_trading_hours(self):
        """Check trading hours for all users and manage positions accordingly"""
        while self.running:
            try:
                active_users = await self.user_service.get_active_users()
                for user_id, user in active_users.items():
                    trading_hours = user.get("settings", {}).get("preferred_trading_hours", {})
                    start_time = trading_hours.get("start")
                    end_time = trading_hours.get("end")
                    
                    if not start_time or not end_time:
                        continue
                    
                    is_trading_time = is_within_trading_hours(start_time, end_time)
                    user_positions = await self.redis_client.get_hash(
                        HashSets.POSITION_USER_MAPPINGS.value, 
                        user_id
                    ) or []
                    
                    # If outside trading hours and has positions, exit all positions
                    if not is_trading_time and user_positions:
                        logger.warning(f"Outside trading hours for user {user_id}, closing all positions")
                        await self.trading_service.exit_all_positions_for_user(user_id)
                    
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error checking trading hours: {e}")
                await asyncio.sleep(60) 

    async def start_listening(self):
        """Start listening to Redis channels"""
        self.running = True
        self.pubsub = self.redis_client.pubsub
        await self.pubsub.subscribe(*self.channels)
        logger.info(f"Started listening to channels: {self.channels}")

        while self.running:
            try:
                message = await self.pubsub.get_message()

                if message and message['type'] == 'message':
                    channel = message['channel'].decode('utf-8')
                    data = json.loads(message['data'])

                    if channel == 'signals':
                        signal_data = data.get('data')
                        signal_key = signal_data.get('identifier')
                        # logger.info(f"Received signal: {signal_data}")
                        # Store signal in Redis for persistence
                        # await self.redis_client.set_hash("signals", signal_key, signal_data)
                        
                        # Process the signal if it hasn't been processed yet
                        await self._process_signal(signal_key, signal_data)
                    
                    logger.debug(f"Received event from channel '{channel}': {signal_data}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding message: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await asyncio.sleep(1)
                continue

        # await asyncio.sleep(0.1) # Preventing CPU overload, for pussies

    async def _process_signal(self, signal_key: str, signal_data: dict):
        eligible_orders = []
        active_users = await self.user_service.get_active_users()
        for user_id, user in active_users.items():
            if await self._is_user_eligible(user_id, signal_data):
                order = await self._create_order_for_user(user, signal_data)
                if order:
                    eligible_orders.append(order)
        
        if eligible_orders:
            await self._execute_orders(eligible_orders)


    async def _is_user_eligible(self, user_id: str, signal_data: dict) -> bool:
        user = await self.user_service.get_user(user_id)
        if not user:
            return False

        # Check trading hours first
        trading_hours = user.get("settings", {}).get("preferred_trading_hours", {})
        start_time = trading_hours.get("start")
        end_time = trading_hours.get("end")
        
        if start_time and end_time and not is_within_trading_hours(start_time, end_time):
            logger.info(f"Outside trading hours for user {user_id}")
            return False
            
        # Get user's current positions and capital
        # logger.info(f"Processing signal for user: {user}")

        if not self._fits_user_risk_management(user, signal_data):
            # logger.info(f"User {user_id} does not fit risk management")
            return False

        identifier = self.redis_client._generate_key(signal_data)
    
        user_position_ids = await self.redis_client.get_hash(HashSets.POSITION_USER_MAPPINGS.value, user_id) or []
        # this method will be inefficient as users and their positions scale because maybe existing_position_ids will be a large list
        existing_position_ids = await self.redis_client.get_hash(HashSets.POSITION_ID_MAPPINGS.value, identifier) or []
    
        # Check if user has any position for this identifier
        if set(existing_position_ids) & set(user_position_ids):
            # logger.info(f"User {user_id} already has a position for identifier {identifier}. It will be updated")
            return False
        
        # logger.info(f"User positions: {user_positions}")

        # Check if user has reached max positions
        if len(user_position_ids) >= user.get('risk_management', {}).get('max_open_positions', 0):
            # logger.info(f"User {user_id} has reached max open positions")
            return False

        # Check if risk-reward ratio matches user's preferences
        signal_rr_ratio = (signal_data["target_price"] - signal_data["entry_price"]) / \
                         (signal_data["entry_price"] - signal_data["stop_loss"])
        
        # logger.info(f"Signal RR ratio: {signal_rr_ratio}")
        # logger.info(f"User ideal RR ratio: {user.get('risk_management', {}).get('ideal_risk_reward_ratio', 0)}")

        if signal_rr_ratio < user.get('risk_management', {}).get('ideal_risk_reward_ratio', 0):
            # logger.info("Signal RR ratio does not match user's preferences")
            return False

        # logger.info("User is eligible")
        return True

    def _fits_user_risk_management(self, user: dict, signal_data: dict) -> bool:
        """
        Determines if the trading signal aligns with the user's risk management preferences.

        Args:
            user (dict): User information including risk management settings.
            signal_data (dict): Trade details including target price, entry price, and stop loss.

        Returns:
            bool: True if the trade fits the user's risk management, False otherwise.
        """
        try:
            # Extract required data
            entry_price = signal_data.get('entry_price')
            stop_loss = signal_data.get('stop_loss')
            target_price = signal_data.get('target_price')
            risk_reward_ratio = user.get('risk_management', {}).get('ideal_risk_reward_ratio')

            # Validate necessary inputs
            if not all([entry_price, stop_loss, target_price, risk_reward_ratio]):
                logger.error("Missing or invalid data for risk calculation.")
                return False
            
            # Calculate profit and loss per lot
            expected_profit_per_lot = target_price - entry_price
            expected_loss_per_lot = entry_price - stop_loss

            # Prevent division by zero
            if expected_loss_per_lot <= 0:
                logger.error("Invalid stop loss or entry price leading to non-positive risk.")
                return False

            # Check risk-reward ratio
            return expected_profit_per_lot / expected_loss_per_lot >= risk_reward_ratio
        except Exception as e:
            logger.error(f"Risk management validation error: {e}")
            return False

    async def _create_order_for_user(self, user: User, signal_data: dict) -> dict:
        try:
            # Get the first active broker for the user
            broker = user["active_brokers"][0] if user["active_brokers"] else None

            if not broker:
                logger.error(f"No active broker found for user {user['_id']}")
                return None

            order = {
                # "validity_ttl": 2,
                "validity": Validity.DAY.value,
                "variety": Variety.REGULAR.value,
                "exchange": Exchange.NFO.value,
                "product": Product.MIS.value,
                "order_type": OrderType.LIMIT.value,
                "tradingsymbol": signal_data["symbol"],
                "user_id": user["_id"],
                "broker": broker,
                "identifier": redis_client._generate_key(signal_data),
                "lot_size": signal_data.get("lot_size"),
                "symbol": signal_data["symbol"],
                "strike_price": signal_data.get("strike_price"),
                "expiry_date": signal_data.get("expiry_date"),
                "right": signal_data.get("right", "CE"),
                "entry_price": signal_data["entry_price"],
                "stop_loss": signal_data["stop_loss"],
                "target": signal_data["target_price"],
                "transaction_type": signal_data.get("transaction_type", TransactionType.BUY.value),
                "position_type": "LONG" if signal_data.get("transaction_type", "BUY") == "BUY" else "SHORT",
                "guid": f"alphaedge_{generate_id()}",
                "status": OrderStatus.OPEN.value
            }
            
            # Calculate position size based on user's risk management settings
            quantity, required_capital = await self._calculate_position_size(user, order)

            if quantity == 0:
                # logger.warning("Calculated position size is 0. Skipping trade.")
                return None

            order["quantity"] = quantity
            order["capital_to_block"] = required_capital

            # logger.info(f"Created order for user {user['_id']}: {order}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return None

    async def _calculate_position_size(self, user: dict, order: dict) -> Tuple[int, float]:
        """
        Calculate the position size based on user's risk management preferences and trade signal.

        Args:
            user (dict): User data containing capital and risk management settings.
            signal_data (dict): Trade signal with entry price, stop-loss, and lot size.

        Returns:
            int: Calculated position size (quantity), or 0 if calculation fails.
        """
        try:
            # Extract user's risk and capital settings
            risk_settings = user.get("risk_management", {})
            capital = user.get("capital", {})

            # Validate required fields
            available_balance = capital.get("available_balance")
            if available_balance is None or available_balance <= 0:
                raise ValueError("Invalid or insufficient available balance.")

            open_positions_count = risk_settings.get("open_positions", 0)
            if open_positions_count >= risk_settings.get("max_open_positions", 0):
                raise ValueError("User has reached the maximum number of open positions.")

            available_capital_per_position = available_balance / (risk_settings.get("max_open_positions", 0) - open_positions_count)
            
            if available_capital_per_position is None or available_capital_per_position <= 0:
                raise ValueError("Invalid or insufficient available capital per position.")

            risk_per_trade_percent = risk_settings.get("ideal_risk_reward_ratio", 2.5)
            stop_loss_buffer = risk_settings.get("stop_loss_buffer", 0.5)
            lot_size = int(order.get("lot_size", 1))

            # TODO: Add this later, refer docs/position_sizing_methods.md
            # position_sizing_method = risk_settings.get("position_sizing_method", "fixed")
            
            # Validate trade signal
            entry_price = order.get("entry_price")
            stop_loss = order.get("stop_loss")
            if entry_price is None or stop_loss is None:
                raise ValueError("Missing entry or stop-loss price in signal data.")

            entry_price = float(entry_price)
            stop_loss = float(stop_loss)

            # Calculate risk per trade and adjusted stop-loss
            risk_per_trade = available_capital_per_position * (risk_per_trade_percent / 100)
            adjusted_stop_loss = stop_loss * (1 - stop_loss_buffer / 100)
            risk_per_unit = abs(entry_price - adjusted_stop_loss)

            if risk_per_unit <= 0:
                raise ValueError("Invalid stop-loss or entry price resulting in zero risk per unit.")

            # Calculate position size
            quantity = risk_per_trade / risk_per_unit

            # Align with lot size
            quantity = max(1, int(quantity // lot_size) * lot_size)

            if quantity < lot_size:
                logger.warning("Calculated position size is less than one lot. Skipping trade.")
                return 0, 999999999999  # Skip trade

            quantity = min(quantity, MAX_POSITION_SIZE)
            order["quantity"] = quantity

            # Check if user has enough capital
            required_capital = await self._calculate_required_capital(order, user["_id"])
            if not await self.user_service.can_block_capital(user["_id"], required_capital):
                return 0, 999999999999

            return quantity, required_capital

        except ValueError as e:
            logger.warning(f"Position size calculation issue: {e}")
            return 0, 999999999999
        except Exception as e:
            logger.error(f"Unexpected error during position size calculation: {e}")
            return 0, 999999999999

    async def _calculate_required_capital(self, order: dict, user_id: str) -> float:      
        if order.get("broker") == Broker.PAPER_BROKER.value:
            return order.get('entry_price') * order.get('quantity')
        
        broker_client = self.trading_service.get_broker_client(
            user_id, 
            order.get("broker")
        )

        if not broker_client:
            logger.error("No broker client available")
            return order.get('entry_price', 0) * order.get('lot_size')
        
        # Form and place the order
        order = {
            **order,
            "transaction_type": order.get('transaction_type', TransactionType.BUY.value),
            "validity": Validity.DAY.value,
            "variety": Variety.REGULAR.value,
            "order_type": OrderType.LIMIT.value,
            "exchange": Exchange.NFO.value,
            "quantity": order.get('quantity'),
            "price": order.get('entry_price')
        }
        required_capital = await broker_client.get_required_margin(order)
        return required_capital

    async def _execute_orders(self, orders: List[Dict]):
        for order in orders:
            try:
                # Place order with broker
                order_id = await self._place_order(order)

                if not order_id:
                    logger.error(f"Failed to place order: {order}")
                    continue
                
                # Calculate capital to block
                capital_to_block = order["capital_to_block"]
                
                # Block capital
                await self.user_service.block_capital(
                    user_id=order["user_id"], 
                    amount=capital_to_block
                )
                
                position_id = None

                if order.get("broker") == Broker.PAPER_BROKER.value:
                    order_data = {
                        **order,
                        "order_id": order_id,
                        "status": OrderStatus.PENDING.value,
                        "created_at": datetime.now().isoformat()
                    }
                    await asyncio.gather(
                        self.redis_client.set_hash(HashSets.ORDERS_PENDING.value, order_id, order_data),
                        self._update_redis_mapping(
                            HashSets.ORDER_ID_MAPPING.value,
                            order["identifier"],
                            order_id
                        )
                    )

                # Save order to MongoDB
                order_to_save = {
                    **order,
                    "order_id": order_id,
                    "created_at": get_ist_time()
                }

                if position_id:
                    order_to_save["position_id"] = position_id

                await self.db[Collections.ORDERS.value].insert_one(order_to_save)
                #logger.info(f"Saved order to MongoDB: {order_result}")
                
            except Exception as e:
                logger.error(f"Error executing order: {e}")

    async def _place_order(self, order: dict) -> dict:
        try:
            # Use the initialized trading service instance
            broker_client = self.trading_service.get_broker_client(
                order["user_id"], 
                order["broker"]
            )

            if not broker_client:
                raise Exception("No broker client available")
            
            # Form and place the order
            formatted_order = await broker_client.form_order(order, is_exit=False)
            order_result = await broker_client.place_order(formatted_order)
            
            if not order_result:
                raise Exception("Order placement failed")
            
            return order_result
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    async def _update_redis_mapping(self, hash_set: str, key: str, value: str):
        """
        Update a Redis hash set mapping by adding a new value to the existing set
        
        Args:
            hash_set (str): The Redis hash set to update
            key (str): The key within the hash set
            value (str): The value to add to the set
        """
        mapping = await self.redis_client.get_hash(hash_set, key) or []
        mapping_set = set(mapping)
        mapping_set.add(value)
        mapping = list(mapping_set)
        await self.redis_client.set_hash(hash_set, key, mapping)

    async def stop_listening(self):
        """Gracefully stop the service"""
        try:
            self.running = False
            if hasattr(self, 'pubsub') and self.pubsub:
                await self.pubsub.unsubscribe(*self.channels)
                await self.pubsub.close()
            
            if self.redis_client and self.redis_client.client:
                await self.redis_client._disconnect()
                
            logger.info("Signal processing service stopped")
        except Exception as e:
            logger.error(f"Error stopping signal processing service: {e}")