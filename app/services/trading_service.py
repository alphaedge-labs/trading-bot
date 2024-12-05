import json
import asyncio
from loguru import logger
from database.redis import redis_client
from database.mongodb import db
from datetime import datetime

from constants.brokers import Broker
from constants.redis import HashSets
from constants.positions import PositionStatus
from brokers.kotak_neo import KotakNeo
from brokers.paper_broker import PaperBroker
from constants.collections import Collections
class TradingService:
    def __init__(self):
        # Create a dedicated pubsub connection
        self.redis_client = redis_client.get_new_connection()
        self.channels = ["positions"]
        self.running = False
        self.broker_clients = {}

    async def start(self):
        """Get all active users from MongoDB"""
        users_collection = db['users']
        active_users = users_collection.find({"is_active": True}).to_list(length=None)
        self.users = {user["_id"]: user for user in active_users}

        # Initialize broker clients for each user's active brokers
        for user_id, user in self.users.items():
            self.broker_clients[user_id] = {}
            
            # Only initialize clients for active brokers
            for broker_config in user["trading"]:
                if broker_config["TRADING_BROKER"] in user["active_brokers"]:
                    if broker_config["TRADING_BROKER"] == Broker.PAPER_BROKER.value:
                        self.broker_clients[user_id][Broker.PAPER_BROKER.value] = PaperBroker(
                            client_id=user["_id"],
                            client_secret=user["email"]
                        )
        
        logger.info(f"Initialized broker clients for {len(self.broker_clients)} users")

        self.running = True
        await self.start_listening()
        
    def get_broker_client(self, user_id: str, broker_name: str):
        """Helper method to get specific broker client for a user"""
        if user_id not in self.broker_clients:
            logger.error(f"No broker clients found for user {user_id}")
            return None
        
        if broker_name not in self.broker_clients[user_id]:
            logger.error(f"Broker {broker_name} not found for user {user_id}")
            return None
            
        return self.broker_clients[user_id][broker_name]

    async def manage_positions(self, data):
        """Manage positions for a user"""
        user_id = data.get("user_id")
        position_id = data.get("position_id")
        
        try:
            # Get position data
            position_data = await self.redis_client.get_hash(HashSets.POSITIONS.value, position_id)

            if not position_data:
                logger.error(f"Position {position_id} not found")
                return
            
            logger.info(f"cp: {position_data['current_price']}, tp: {position_data['take_profit']}, sl: {position_data['stop_loss']}")

            if position_data.get("should_exit") == True:
                # Get the appropriate broker client
                broker_client = self.get_broker_client(user_id, position_data["broker"])
                if not broker_client:
                    return
                    
                # Place exit order
                exit_order = broker_client.form_order(position_data, True)
                try:
                    # Place the exit order
                    order_result = await broker_client.place_order(exit_order)
                    
                    # Calculate realized P&L
                    entry_price = float(position_data["entry_price"])
                    exit_price = float(order_result["current_price"])
                    quantity = float(position_data["quantity"])
                    realized_pnl = (exit_price - entry_price) * quantity
                    
                    # Store closed position in MongoDB
                    closed_position = {
                        **position_data,
                        "exit_price": exit_price,
                        "exit_time": datetime.now().isoformat(),
                        "realized_pnl": realized_pnl,
                        "order_result": order_result,
                        "status": "CLOSED"
                    }
                    
                    await db[Collections.CLOSED_POSITIONS.value].insert_one(closed_position)
                    
                    # Update user's capital and metrics
                    user = self.users[user_id]
                    await self._update_user_metrics(user_id, realized_pnl, position_data)
                    
                    # Remove position from Redis
                    await self._cleanup_position(position_id, position_data)
                    
                    # logger.info(f"Successfully closed position {position_id} for user {user_id}")
                    
                except Exception as e:
                    logger.error(f"Error executing exit order for position {position_id}: {e}")
                    # Mark position as failed_exit
                    position = await self.redis_client.get_hash(HashSets.POSITIONS.value, position_id)
                    if not position:
                        logger.error(f"Position {position_id} not found")
                        return
                    
                    # Extend the position object with additional fields
                    position["status"] = PositionStatus.EXIT_FAILED.value
                    position["error"] = str(e)

                    # Save the updated position back to Redis using set_hash
                    await self.redis_client.set_hash(HashSets.POSITIONS.value, position_id, position)

                    
        except Exception as e:
            logger.error(f"Error managing position {position_id}: {e}")

    async def _update_user_metrics(self, user_id: str, realized_pnl: float, position_data: dict):
        """Update user's capital and trading metrics"""
        try:
            # Update user document in MongoDB
            await db["users"].update_one(
                {"_id": user_id},
                {
                    "$inc": {
                        "capital.available_balance": realized_pnl,
                        "capital.total_deployed": -abs(float(position_data.get("quantity", 0)))
                    },
                    "$push": {
                        "activity_logs": {
                            "timestamp": datetime.now(),
                            "activity": f"Position closed with P&L: {realized_pnl}"
                        }
                    }
                }
            )
            
            # Update user's data in memory
            self.users[user_id]["capital"]["available_balance"] += realized_pnl
            
        except Exception as e:
            logger.error(f"Error updating user metrics for {user_id}: {e}")

    # TODO: this function is handling cleaning both position_ids and position_user_ids, can split this into two functions for better readability and handling
    async def _cleanup_position(self, position_id: str, position_data: dict):
        """Clean up position data from Redis"""
        try:
            # Remove from positions hash
            await self.redis_client.delete_hash(HashSets.POSITIONS.value, position_id)
            
            # Remove from position mapping
            identifier = await self.redis_client._generate_key(position_data)

            position_ids_mapping = await self.redis_client.get_hash(HashSets.POSITION_ID_MAPPINGS.value, identifier) or []
            position_ids_set = set(position_ids_mapping)
            position_ids_set.discard(position_id)
            position_ids = list(position_ids_set)
            
            if position_ids:
                await self.redis_client.set_hash(HashSets.POSITION_ID_MAPPINGS.value, identifier, {
                    "position_ids": ",".join(position_ids)
                })
            else:
                await self.redis_client.delete_hash(HashSets.POSITION_ID_MAPPINGS.value, identifier)


            position_user_ids_mapping = await self.redis_client.get_hash(HashSets.POSITION_USER_MAPPINGS.value, position_data["user_id"]) or []
            position_user_ids_set = set(position_user_ids_mapping)
            position_user_ids_set.discard(position_id)
            position_user_ids = list(position_user_ids_set)

            if position_user_ids:
                await self.redis_client.set_hash(HashSets.POSITION_USER_MAPPINGS.value, position_data["user_id"], {
                    "position_user_ids": ",".join(position_user_ids)
                })
            else:
                await self.redis_client.delete_hash(HashSets.POSITION_USER_MAPPINGS.value, position_data["user_id"])

        except Exception as e:
            logger.error(f"Error cleaning up position {position_id}: {e}")

    async def manage_risk(self, data):
        """Manage risk for a user"""
        try:
            user_id = data.get("user_id")
            user = self.users.get(user_id)
            
            if not user:
                logger.error(f"User {user_id} not found")
                return
            
            # Get all open positions for user
            positions_keys = await self.redis_client.get_hash(HashSets.POSITION_USER_MAPPINGS.value, user_id) or []
            total_risk = 0
            
            for position_key in positions_keys:
                position = await self.redis_client.get_hash(HashSets.POSITIONS.value, position_key)
                if not position:
                    continue
                unrealized_pnl = float(position.get("unrealized_pnl", 0))
                total_risk += abs(unrealized_pnl)
                
            # Check if total risk exceeds user's risk limits
            max_risk = user.get("risk_management", {}).get("max_risk_per_day", float('inf'))
            
            if total_risk > max_risk:
                logger.warning(f"Risk limit exceeded for user {user_id}. Closing all positions.")
                await self.exit_all_positions()
                
        except Exception as e:
            logger.error(f"Error managing risk: {e}")

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
                    decoded_data = json.loads(message['data'].decode('utf-8'))
                    
                    if channel == "positions":
                        await self.manage_positions(decoded_data["data"])
                        
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await asyncio.sleep(1)
                continue
                
            await asyncio.sleep(0.1)

    async def exit_all_positions(self):
        """Exit all open positions for a user"""
        try:
            # Get all open positions for user
            positions = await self.redis_client.get_all_keys(HashSets.POSITIONS.value)
            # logger.info(f"Found {len(positions)} positions to close")

            for position in positions:
                try:
                    # Create exit order
                    exit_order = {
                        "user_id": position["user_id"],
                        "broker": position["broker"],
                        "symbol": position["symbol"],
                        "strike_price": position.get("strike_price"),
                        "expiry_date": position.get("expiry_date"),
                        "right": position.get("right"),
                        "quantity": position["quantity"],
                        "order_type": "MARKET",
                        "transaction_type": "SELL" if position["position_type"] == "LONG" else "BUY",
                        "product": position["product"],
                        "timestamp": datetime.now().isoformat()
                    }

                    # Process exit order through manage_positions
                    await self.manage_positions({
                        "action": "EXIT",
                        "position_id": position["position_id"],
                        "order": exit_order
                    })
                    
                    # logger.info(f"Initiated exit for position {position['position_id']}")
                    
                except Exception as e:
                    logger.error(f"Error exiting position {position['position_id']}: {e}")
                    continue

            logger.info(f"Successfully closed all positions for users")
            
        except Exception as e:
            logger.error(f"Error in exit_all_positions: {e}")
            raise
        
    async def stop_listening(self):
        """Stop listening to Redis channels"""
        self.running = False
        await self.redis_client.pubsub.unsubscribe(*self.channels)
        logger.info("Stopped listening to Redis channels") 
