import json
import asyncio
from loguru import logger
from datetime import datetime

from database.mongodb import db
from database.redis import redis_client

from services.user_service import UserService

from constants.collections import Collections
from constants.brokers import Broker
from constants.redis import HashSets
from constants.positions import PositionStatus

from brokers.kotak_neo import KotakNeo
from brokers.paper_broker import PaperBroker

from utils.id_generator import generate_id
from utils.datetime import _parse_datetime

class TradingService:
    def __init__(self, user_service: UserService):
        # Create a dedicated pubsub connection
        self.user_service = user_service
        self.redis_client = redis_client.get_new_connection()
        self.channels = ["positions"]
        self.running = False
        self.broker_clients = {}
        self.positions_collection = db[Collections.CLOSED_POSITIONS.value]
        self.users_collection = db[Collections.USERS.value]

    async def start(self):
        """Get all active users and initialize broker clients"""
        active_users = await self.user_service.get_active_users()

        # Initialize broker clients for each user's active brokers
        for user_id, user in active_users.items():
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
                logger.error(f"Position {position_id} not found to manage")
                return
            
            logger.info(f"user_id: {user_id}, position_id: {position_id}, pnl: {position_data['unrealized_pnl']}")

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
                    
                    # Release blocked capital
                    blocked_capital = float(position_data.get("blocked_capital", 0))

                    # Calculate realized P&L
                    entry_price = float(position_data["entry_price"])
                    exit_price = float(order_result["average_price"])
                    quantity = float(position_data["quantity"])
                    realized_pnl = (exit_price - entry_price) * quantity

                    # Store closed position in MongoDB
                    closed_position = {
                        **position_data,
                        "_id": f"clpos_{generate_id()}",
                        "exit_price": exit_price,
                        "exit_time": datetime.now(),
                        "timestamp": _parse_datetime(position_data["timestamp"]),
                        "last_updated": _parse_datetime(position_data["last_updated"]),
                        "realized_pnl": realized_pnl,
                        "order_result": order_result,
                        "status": "CLOSED"
                    }

                    await self.positions_collection.insert_one(closed_position)
                    # Release blocked capital and update capital with realized PnL
                    await self.user_service.release_capital(
                        user_id=position_data["user_id"], 
                        blocked_capital=blocked_capital,
                        pnl=realized_pnl
                    )

                    identifier = self.redis_client._generate_key(position_data)
                    await asyncio.gather(
                        # Remove from positions hash
                        self.redis_client.delete_hash(HashSets.POSITIONS.value, position_id),
                        # Clean up position ID mapping
                        self._cleanup_mapping(HashSets.POSITION_ID_MAPPINGS.value, identifier, position_id),
                        # Clean up position user mapping
                        self._cleanup_mapping(HashSets.POSITION_USER_MAPPINGS.value, position_data["user_id"], position_id)
                    )
                    
                    logger.info(f"Closed position {position_id} for user {user_id} with P&L: {realized_pnl}")
                    
                except Exception as e:
                    logger.error(f"Error executing exit order for position {position_id}: {e}")
                    # Mark position as failed_exit
                    position = await self.redis_client.get_hash(HashSets.POSITIONS.value, position_id)
                    if not position:
                        logger.error(f"Position {position_id} not found to exit")
                        return
                    
                    # Extend the position object with additional fields
                    position["status"] = PositionStatus.EXIT_FAILED.value
                    position["error"] = str(e)

                    # Save the updated position back to Redis using set_hash
                    await self.redis_client.set_hash(HashSets.POSITIONS.value, position_id, position)

                    
        except Exception as e:
            logger.error(f"Error managing position {position_id}: {e}")

    async def _cleanup_mapping(self, hash_set: HashSets, key: str, position_id: str):
        """Helper method to clean up Redis hash mappings"""
        try:
            mapping = await self.redis_client.get_hash(hash_set.value, key) or []
            mapping_set = set(mapping)
            mapping_set.discard(position_id)
            mapping_list = list(mapping_set)

            if mapping_list:
                await self.redis_client.set_hash(hash_set.value, key, mapping_list)
            else:
                await self.redis_client.delete_hash(hash_set.value, key)
        except Exception as e:
            logger.error(f"Error cleaning up mapping for {hash_set.value}/{key}: {e}")

    async def manage_risk(self, data):
        """Manage risk for a user"""
        try:
            user_id = data.get("user_id")
            user = await self.user_service.get_user(user_id)
            
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

    async def exit_all_positions_for_user(self, user_id: str):
        """Exit all open positions for a specific user"""
        try:
            # Get all positions for user
            position_ids = await self.redis_client.get_hash(
                HashSets.POSITION_USER_MAPPINGS.value, 
                user_id
            ) or []
            
            for position_id in position_ids:
                position_data = await self.redis_client.get_hash(
                    HashSets.POSITIONS.value, 
                    position_id
                )
                if position_data:
                    position_data["should_exit"] = True
                    await self.redis_client.set_hash(
                        HashSets.POSITIONS.value,
                        position_id,
                        position_data
                    )
                    
                    # Process the exit
                    await self.manage_positions({
                        "user_id": user_id,
                        "position_id": position_id
                    })
                    
            logger.info(f"Exited all positions for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error exiting positions for user {user_id}: {e}")
        