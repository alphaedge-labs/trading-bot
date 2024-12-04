import json
import asyncio
from loguru import logger
from database.redis import redis_client
from database.mongodb import db
from datetime import datetime

from constants.brokers import Broker
from brokers.kotak_neo import KotakNeo
from brokers.paper_broker import PaperBroker

class TradingService:
    def __init__(self):
        self.pubsub = redis_client.get_pubsub()
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
                    if broker_config["TRADING_BROKER"] == Broker.KOTAK_NEO:
                        self.broker_clients[user_id][Broker.KOTAK_NEO] = KotakNeo(
                            client_id=broker_config["TRADING_CLIENT_ID"],
                            client_secret=broker_config["TRADING_SECRET_KEY"]
                        )
                    elif broker_config["TRADING_BROKER"] == Broker.PAPER_BROKER:
                        self.broker_clients[user_id][Broker.PAPER_BROKER] = PaperBroker(
                            client_id=user["_id"],
                            client_secret=user.get("email", user.get("phone", ""))
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
        position_id = data.get("identifier")
        
        try:
            # Get position data
            position_data = await redis_client.get_hash("positions", position_id)
            
            if position_data.get("should_exit") == "True":
                # Get the appropriate broker client
                broker_client = self.get_broker_client(user_id, position_data["broker"])
                if not broker_client:
                    return
                    
                # Place exit order
                exit_order = broker_client.form_order(position_data, True)
                # exit_order = {
                #     "symbol": position_data["symbol"],
                #     "quantity": position_data["quantity"],
                #     "order_type": "MARKET",
                #     "transaction_type": "SELL" if position_data["position_type"] == "LONG" else "BUY",
                #     "product": "MIS"
                # }
                
                try:
                    # Place the exit order
                    order_result = await broker_client.place_order(exit_order)
                    
                    # Calculate realized P&L
                    entry_price = float(position_data["entry_price"])
                    exit_price = float(order_result["average_price"])
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
                    
                    await db["closed_positions"].insert_one(closed_position)
                    
                    # Update user's capital and metrics
                    user = self.users[user_id]
                    await self._update_user_metrics(user_id, realized_pnl, position_data)
                    
                    # Remove position from Redis
                    await self._cleanup_position(position_id, position_data)
                    
                    logger.info(f"Successfully closed position {position_id} for user {user_id}")
                    
                except Exception as e:
                    logger.error(f"Error executing exit order for position {position_id}: {e}")
                    # Mark position as failed_exit
                    await redis_client.update_hash("positions", position_id, {
                        "status": "EXIT_FAILED",
                        "error": str(e)
                    })
                    
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

    async def _cleanup_position(self, position_id: str, position_data: dict):
        """Clean up position data from Redis"""
        try:
            # Remove from positions hash
            await redis_client.delete_hash("positions", position_id)
            
            # Remove from position mapping
            identifier = f"{position_data['symbol']}:{position_data['expiry_date']}:{position_data['right']}:{position_data['strike_price']}"
            mapping = await redis_client.get_hash("position_mappings", identifier) or {}
            position_ids = set(mapping.get("position_ids", "").split(","))
            position_ids.discard(position_id)
            
            if position_ids:
                await redis_client.set_hash("position_mappings", identifier, {
                    "position_ids": ",".join(position_ids)
                })
            else:
                await redis_client.delete_hash("position_mappings", identifier)
                
        except Exception as e:
            logger.error(f"Error cleaning up position {position_id}: {e}")

    async def manage_risk(self, data):
        """Manage risk for a user"""
        pass

    async def start_listening(self):
        """Start listening to Redis channels"""
        self.running = True
        await self.pubsub.subscribe(*self.channels)
        logger.info(f"Started listening to channels: {self.channels}")
        
        while self.running:
            try:
                message = await self.pubsub.get_message()
                if message and message['type'] == 'message':
                    channel = message['channel'].decode('utf-8')
                    decoded_data = json.loads(message['data'].decode('utf-8'))
                    data = {
                        "type": channel,
                        "action": decoded_data["action"],
                        "category": decoded_data["category"],
                        "data": decoded_data["data"]
                    }
                    logger.info(f"Received event from channel '{channel}': {data}")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await asyncio.sleep(1)
                continue
                
            await asyncio.sleep(0.1) # Prevent CPU overload

    async def exit_all_positions(self):
        positions = await redis_client.get_all_keys("positions")
        for position in positions:
            await self.manage_positions(position)

    async def stop_listening(self):
        """Stop listening to Redis channels"""
        self.running = False
        await self.pubsub.unsubscribe()
        logger.info("Stopped listening to Redis channels") 
