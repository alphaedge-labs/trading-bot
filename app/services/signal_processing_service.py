import json
import asyncio
from typing import Dict, List
from loguru import logger
from datetime import datetime

from models.user import User
from database.redis import redis_client
from database.mongodb import db
from services.trading_service import TradingService
from constants.redis import HashSets
from constants.collections import Collections
from utils.id_generator import generate_id
from utils.datetime import is_within_trading_hours

class SignalProcessingService:
    def __init__(self):
        # Create a dedicated pubsub connection
        self.redis_client = redis_client.get_new_connection()
        self.channels = ["signals"]
        self.running = False
        self.users: Dict[str, User] = {}
        self.trading_service = TradingService()

    async def start(self):
        logger.info("Starting signal processing service")
        if self.running:
            logger.warning("Signal processing service is already running")
            return

        # Load users
        await self._load_users()

        logger.info("Starting to listen for signals and trading service")
        # Run trading service start, listening for signals, and trading hours check concurrently
        await asyncio.gather(
            self.trading_service.start(),
            self.start_listening(),
            self._check_trading_hours()
        )

    async def _load_users(self):
        users_collection = db['users']
        active_users = users_collection.find({"is_active": True}).to_list(length=None)
        self.users = {user["_id"]: user for user in active_users}

    async def _create_order_for_user(self, user: User, signal_data: dict) -> dict:
        try:
            # Calculate position size based on user's risk management settings
            quantity = self._calculate_position_size(user, signal_data)
            
            # Get the first active broker for the user
            broker = user["active_brokers"][0] if user["active_brokers"] else None
            if not broker:
                logger.error(f"No active broker found for user {user['_id']}")
                return None

            order = {
                "user_id": user["_id"],
                "broker": broker,
                "symbol": signal_data["symbol"],
                "strike_price": signal_data.get("strike_price"),
                "expiry_date": signal_data.get("expiry_date"),
                "right": signal_data.get("right", "CE"),
                "quantity": quantity,
                "entry_price": signal_data["entry_price"],
                "stop_loss": signal_data["stop_loss"],
                "target": signal_data["target_price"],
                "order_type": "LIMIT",
                "transaction_type": signal_data.get("transaction_type", "BUY"),
                "product": "MIS",
                "position_type": "LONG" if signal_data.get("transaction_type", "BUY") == "BUY" else "SHORT",
                "timestamp": datetime.now().isoformat()
            }
            
            # logger.info(f"Created order for user {user['_id']}: {order}")
            return order
            
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return None

    def _calculate_position_size(self, user: User, signal_data: dict) -> int:
        try:
            # Get user's risk management settings
            risk_settings = user.get("risk_management", {})
            capital = user.get("capital", {})
            
            # Extract required values
            available_balance = capital.get("available_balance", 0)
            risk_per_trade_percent = risk_settings.get("risk_per_trade", 1)  # Default 1%
            stop_loss_buffer = risk_settings.get("stop_loss_buffer", 0.5)  # Default buffer
            # TODO: Add this later, refer docs/position_sizing_methods.md
            # position_sizing_method = risk_settings.get("position_sizing_method", "fixed")
            
            
            # Risk amount per trade
            risk_per_trade = available_balance * (risk_per_trade_percent / 100)
            
            # Entry and stop-loss prices
            entry_price = float(signal_data["entry_price"])
            stop_loss = float(signal_data["stop_loss"])
            
            # Adjusted stop loss considering buffer
            adjusted_stop_loss = stop_loss * (1 - stop_loss_buffer / 100)
            risk_per_unit = abs(entry_price - adjusted_stop_loss)
            
            # Calculate position size
            if risk_per_unit == 0:
                raise ValueError("Stop loss and entry price are too close, cannot calculate risk per unit.")
        
            quantity = risk_per_trade / risk_per_unit
        
            # Ensure position size respects the lot size
            lot_size = int(signal_data.get("lot_size", 1))
            quantity = max(1, int(quantity // lot_size) * lot_size)
            
            return quantity

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0

    async def _process_signal(self, signal_key: str, signal_data: dict):
        eligible_orders = []
        for user_id, user in self.users.items():
            if await self._is_user_eligible(user_id, user, signal_data):
                order = await self._create_order_for_user(user, signal_data)
                if order:
                    eligible_orders.append(order)
        
        if eligible_orders:
            await self._execute_orders(eligible_orders)

    def _calculate_required_capital(self, signal_data: dict) -> float:
        logger.info(f"Calculating required capital for signal: {signal_data}")
        # TODO: Add more logic to calculate required capital, this is just for options, also this lot size is hard coded on data-server for nifty 50 options
        return signal_data.get('entry_price', 0) * signal_data.get('lot_size')

    async def _is_user_eligible(self, user_id: str, user: User, signal_data: dict) -> bool:
        # Check trading hours first
        trading_hours = user.get("settings", {}).get("preferred_trading_hours", {})
        start_time = trading_hours.get("start")
        end_time = trading_hours.get("end")
        
        if start_time and end_time and not is_within_trading_hours(start_time, end_time):
            logger.info(f"Outside trading hours for user {user_id}")
            return False
            
        # Get user's current positions and capital
        # logger.info(f"Processing signal for user: {user}")

        identifier = self.redis_client._generate_key(signal_data)
    
        user_position_ids = await self.redis_client.get_hash(HashSets.POSITION_USER_MAPPINGS.value, user_id) or []
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

        # Check if user has enough capital
        required_capital = self._calculate_required_capital(signal_data)
        # logger.info(f"Required capital: {required_capital}")
        if required_capital > user.get('capital', {}).get('available_balance', 0):
            # logger.info("User does not have enough capital")
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
            formatted_order = broker_client.form_order(order, is_exit=False)
            order_result = await broker_client.place_order(formatted_order)
            
            if not order_result:
                raise Exception("Order placement failed")
            
            return order_result
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    async def _execute_orders(self, orders: List[Dict]):
        for order in orders:
            # logger.info(f"Executing order: {order}")
            try:
                # Place order with broker
                order_result = await self._place_order(order)
                #logger.info(f"Order result: {order_result}")
                if not order_result:
                    logger.error(f"Failed to place order: {order}")
                    continue

                # Create position in Redis
                position_id = f"pos_{generate_id()}"
                #logger.info(f"Generated position id: {position_id}")
                identifier = self.redis_client._generate_key(order)
                #logger.info(f"Generated identifier: {identifier}")
                
                position_data = {
                    "position_id": position_id,
                    "user_id": str(order["user_id"]),
                    "symbol": str(order["symbol"]),
                    "right": str(order["right"]),
                    "strike_price": str(order["strike_price"]),
                    "expiry_date": str(order["expiry_date"]),
                    "identifier": identifier,
                    "broker": str(order["broker"]),
                    "position_type": str(order.get("position_type", "LONG")),
                    "quantity": str(order["quantity"]),
                    "entry_price": str(order["entry_price"]),
                    "current_price": str(order["entry_price"]),
                    "unrealized_pnl": "0",
                    "realized_pnl": "0",
                    "stop_loss": str(order["stop_loss"]),
                    "take_profit": str(order["target"]),
                    "timestamp": datetime.now().isoformat(),
                    "status": "OPEN",
                    "should_exit": "False",
                    "last_updated": datetime.now().strftime("%c")
                }
                #logger.info(f"Generated position data: {position_data}")
                
                # Set position data, update position mapping and user mapping concurrently
                await asyncio.gather(
                    self.redis_client.set_hash(HashSets.POSITIONS.value, position_id, position_data),
                    self._update_position_mapping(identifier, position_id),
                    self._update_position_user_mapping(order["user_id"], position_id)
                )
                #logger.info(f"Saved position data, position mapping and user mapping")
                
                # Save order to MongoDB
                db[Collections.ORDERS.value].insert_one({
                    **order,
                    **order_result,
                    "position_id": position_id,
                    "created_at": datetime.now()
                })
                #logger.info(f"Saved order to MongoDB: {order_result}")
                
            except Exception as e:
                logger.error(f"Error executing order: {e}")

    async def _update_position_mapping(self, identifier: str, position_id: str):
        """Update position mapping in Redis"""
        #logger.info(f"Updating position mapping for identifier: {identifier} and position_id: {position_id}")
        mapping = await self.redis_client.get_hash(HashSets.POSITION_ID_MAPPINGS.value, identifier) or []
        #logger.info(f"Current mapping: {mapping}")
        mapping_set = set(mapping)
        mapping_set.add(position_id)
        mapping = list(mapping_set)
        #logger.info(f"Updated mapping: {mapping}")
        await self.redis_client.set_hash(HashSets.POSITION_ID_MAPPINGS.value, identifier, mapping)

    async def _update_position_user_mapping(self, user_id: str, position_id: str):
        """Update position user mapping in Redis"""
        #logger.info(f"Updating position user mapping for user_id: {user_id} and position_id: {position_id}")
        mapping = await self.redis_client.get_hash(HashSets.POSITION_USER_MAPPINGS.value, user_id) or []
        #logger.info(f"Current mapping: {mapping}")
        mapping_set = set(mapping)
        mapping_set.add(position_id)
        mapping = list(mapping_set)
        #logger.info(f"Updated mapping: {mapping}")
        await self.redis_client.set_hash(HashSets.POSITION_USER_MAPPINGS.value, user_id, mapping)

    async def start_listening(self):
        """Start listening to Redis channels"""
        self.running = True
        await self.redis_client.pubsub.subscribe(*self.channels)
        logger.info(f"Started listening to channels: {self.channels}")

        while self.running:
            try:
                message = await self.redis_client.pubsub.get_message()

                if message and message['type'] == 'message':
                    channel = message['channel'].decode('utf-8')
                    data = json.loads(message['data'])

                    if channel == 'signals':
                        signal_data = data.get('data')
                        signal_key = signal_data.get('identifier')
                        #logger.info(f"Received signal: {signal_data}")
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

    async def stop_listening(self):
        """Stop listening to Redis channels"""
        self.running = False
        await self.redis_client.pubsub.unsubscribe(*self.channels)
        logger.info("Stopped listening to Redis channels") 

    async def _check_trading_hours(self):
        """Check trading hours for all users and manage positions accordingly"""
        while self.running:
            try:
                for user_id, user in self.users.items():
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
                        logger.info(f"Outside trading hours for user {user_id}, closing all positions")
                        await self.trading_service.exit_all_positions_for_user(user_id)
                    
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error checking trading hours: {e}")
                await asyncio.sleep(60) 