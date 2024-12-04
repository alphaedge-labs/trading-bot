from typing import Dict, List
from loguru import logger
from database.redis import redis_client
from database.mongodb import db
from models.user import User
import asyncio
import json
from datetime import datetime

class SignalProcessingService:
    def __init__(self):
        self.pubsub = redis_client.get_pubsub()
        self.redis = redis_client
        self.channels = ["signals"]
        self.running = False
        self._processing_task = None
        self.users: Dict[str, User] = {}

    async def start(self):
        logger.info("Starting signal processing service")
        if self.running:
            logger.warning("Signal processing service is already running")
            return
        
        await self._load_users()
        self.running = True

    async def _load_users(self):
        users_collection = db['users']
        active_users = users_collection.find({"is_active": True}).to_list(length=None)
        self.users = {user["_id"]: user for user in active_users}

        await self.start_listening()

    async def _process_signal(self, signal_key: str, signal_data: dict):
        eligible_orders = []
        for user_id, user in self.users.items():
            if await self._is_user_eligible(user, signal_data):
                order = await self._create_order_for_user(user, signal_data)
                if order:
                    eligible_orders.append(order)
        
        if eligible_orders:
            await self._execute_orders(eligible_orders)
            await self.redis.set_hash("signals", signal_key, {"processed": "true"})

    async def _is_user_eligible(self, user: User, signal_data: dict) -> bool:
        # Get user's current positions and capital
        user_positions = await self.redis.get_hash(f"positions:{user._id}", "*")
        
        # Check if user has reached max positions
        if len(user_positions) >= user.risk_management.max_open_positions:
            return False

        # Check if user has enough capital
        required_capital = self._calculate_required_capital(signal_data)
        if required_capital > user.capital.available_balance:
            return False

        # Check if risk-reward ratio matches user's preferences
        signal_rr_ratio = (signal_data["target_price"] - signal_data["entry_price"]) / \
                         (signal_data["entry_price"] - signal_data["stop_loss"])
        if signal_rr_ratio < user.risk_management.ideal_risk_reward_ratio:
            return False

        return True

    async def _execute_orders(self, orders: List[Dict]):
        for order in orders:
            try:
                # Place order with broker
                order_result = await self._place_order(order)
                
                # Create position in Redis
                position_id = f"position_{datetime.now().timestamp()}"
                position_data = {
                    "position_id": position_id,
                    "account_id": order["user_id"],
                    "symbol": order["symbol"],
                    "strike_price": order["strike_price"],
                    "expiry_date": order["expiry_date"],
                    "identifier": f"{order['symbol']}:{order['expiry_date']}:{order['strike_price']}",
                    "position_type": "LONG",
                    "quantity": order["quantity"],
                    "entry_price": order["entry_price"],
                    "current_price": order["entry_price"],
                    "unrealized_pnl": 0.0,
                    "realized_pnl": 0.0,
                    "stop_loss": order["stop_loss"],
                    "take_profit": order["target"],
                    "timestamp": datetime.now().isoformat(),
                    "status": "OPEN",
                    "should_exit": False,
                    "last_updated": datetime.now().strftime("%c")
                }
                
                await self.redis.set_hash("positions", position_id, position_data)
                
                # Update position mapping
                identifier = f"{order['symbol']}:{order['expiry_date']}:{order['right']}:{order['strike_price']}"
                await self._update_position_mapping(identifier, position_id)
                
                # Save order to MongoDB
                await db["orders"].insert_one({
                    **order,
                    **order_result,
                    "position_id": position_id,
                    "created_at": datetime.now()
                })
                
            except Exception as e:
                logger.error(f"Error executing order: {e}")

    async def _update_position_mapping(self, identifier: str, position_id: str):
        mapping = await self.redis.get_hash("position_mappings", identifier) or {}
        position_ids = set(mapping.get("position_ids", "").split(","))
        position_ids.add(position_id)
        await self.redis.set_hash("position_mappings", identifier, {
            "position_ids": ",".join(position_ids)
        })

    async def start_listening(self):
        """Start listening to Redis channels"""
        await self.pubsub.subscribe(*self.channels)
        logger.info(f"Started listening to channels: {self.channels}")
        
        while self.running:
            try:
                message = await self.pubsub.get_message()
                if message and message['type'] == 'message':
                    channel = message['channel'].decode('utf-8')
                    decoded_data = json.loads(message['data'].decode('utf-8'))
                    
                    if channel == 'signals':
                        signal_data = decoded_data.get('data', {})
                        signal_key = signal_data.get('id') or f"signal_{datetime.now().timestamp()}"
                        
                        # Store signal in Redis for persistence
                        await self.redis.set_hash("signals", signal_key, signal_data)
                        
                        # Process the signal if it hasn't been processed yet
                        if not signal_data.get("processed"):
                            await self._process_signal(signal_key, signal_data)
                            logger.info(f"Processed signal: {signal_key}")
                    
                    logger.debug(f"Received event from channel '{channel}': {decoded_data}")
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
        await self.pubsub.unsubscribe()
        logger.info("Stopped listening to Redis channels") 