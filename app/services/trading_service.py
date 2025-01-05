import json
import asyncio
from loguru import logger
from datetime import datetime

from database.manager import DatabaseManager
from database.redis import redis_client

from services.user_service import UserService

from constants.collections import Collections
from constants.brokers import Broker
from constants.redis import HashSets
from constants.positions import PositionStatus
from constants.orders import OrderStatus, Exchange

from brokers.kotak_neo import KotakNeo
from brokers.paper_broker import PaperBroker
from brokers.zerodha_kite import ZerodhaKite

class TradingService:
    def __init__(self, user_service: UserService):
        # Create a dedicated pubsub connection
        self.user_service = user_service
        self.redis_client = redis_client.get_new_connection()
        self.channels = ["positions"]
        self.running = False
        self.broker_clients = {}
        self.db_manager = DatabaseManager()
        self.db = None

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
                        self.broker_clients[user_id][Broker.PAPER_BROKER.value].login(
                            mobilenumber=broker_config["TRADING_CLIENT_ID"],
                            password=broker_config["TRADING_PASSWORD"]
                        )
                        
                    elif broker_config["TRADING_BROKER"] == Broker.KOTAK_NEO.value:
                        self.broker_clients[user_id][Broker.KOTAK_NEO.value] = KotakNeo(
                            client_id=broker_config["TRADING_APP_KEY"],
                            client_secret=broker_config["TRADING_SECRET_KEY"],
                            neo_fin_key=broker_config["TRADING_FIN_KEY"]
                        )
                        self.broker_clients[user_id][Broker.KOTAK_NEO.value].login(
                            mobilenumber=broker_config["TRADING_CLIENT_ID"],
                            password=broker_config["TRADING_PASSWORD"]
                        )
                    
                    elif broker_config["TRADING_BROKER"] == Broker.ZERODHA_KITE.value:
                        self.broker_clients[user_id][Broker.ZERODHA_KITE.value] = ZerodhaKite(
                            client_id=broker_config["TRADING_APP_KEY"],
                            client_secret=broker_config["TRADING_SECRET_KEY"],
                            access_token=broker_config["TRADING_ACCESS_TOKEN"]
                        )
                        await self.broker_clients[user_id][Broker.ZERODHA_KITE.value].login()
                        
        logger.info(f"Initialized broker clients for {len(self.broker_clients)} users")
        self.running = True

        self.db = await self.db_manager.get_db()
    
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
            
            pnl = position_data['unrealized_pnl']
            if pnl > 0:
                logger.success(f'Pnl for user {user_id}: {pnl}')
            else:
                logger.error(f'Pnl for user {user_id}: {pnl}')

            if position_data.get("should_exit") == True:
                # Get the appropriate broker client


                broker_client = self.get_broker_client(user_id, position_data["broker"])
                if not broker_client:
                    return
                
                # Place exit order
                exit_order = await broker_client.form_order(position_data, True)

                try:
                    # Place the exit order
                    order_id = await broker_client.place_order(exit_order)

                    if not order_id:
                        logger.error(f"Failed to place exit order for position {position_id}")
                        return
                    
                    logger.success(f'Placed exit order for user {user_id}')

                    order_to_insert = {
                        **exit_order,
                        "identifier": self.redis_client._generate_key(exit_order),
                        "order_id": order_id,
                        "position_id": position_id,
                        "user_id": user_id,
                        "broker": position_data.get("broker"),
                        "status": OrderStatus.PENDING.value,
                        "exchange": Exchange.NFO.value,
                        "is_exit": True
                    }

                    if order_to_insert.get("broker") == Broker.PAPER_BROKER.value:
                        await asyncio.gather(
                            self.redis_client.set_hash(HashSets.ORDERS_PENDING.value, order_id, order_to_insert),
                            self._update_redis_mapping(
                                HashSets.ORDER_ID_MAPPING.value,
                                order_to_insert["identifier"],
                                order_id
                            )
                        )

                    await self.db[Collections.ORDERS.value].insert_one(order_to_insert)

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
        """Gracefully stop the service"""

        logger.warning("Stopping trading service...")
        all_user_ids = await self.redis_client.get_all_keys(HashSets.POSITION_USER_MAPPINGS.value)
        for user_id in all_user_ids:
            logger.info(f"Exiting all positions for user {user_id}")
            await self.exit_all_positions_for_user(user_id)

        # Wait for all positions to close
        positions = await self.redis_client.get_all_keys(HashSets.POSITIONS.value)
        while len(positions) > 0:
            logger.info(f"Waiting for {len(positions)} positions to close...")
            await asyncio.sleep(5)
            positions = await self.redis_client.get_all_keys(HashSets.POSITIONS.value)

        try:
            self.running = False
            if hasattr(self, 'pubsub') and self.pubsub:
                await self.pubsub.unsubscribe(*self.channels)
                await self.pubsub.close()
            
            if self.redis_client and self.redis_client.client:
                await self.redis_client._disconnect()
                
            logger.info("Trading service stopped")
        except Exception as e:
            logger.error(f"Error stopping trading service: {e}")

    async def _remove_position_mappings(self, position_id: str, user_id: str, identifier: str):
        """Remove position from all mappings"""
        try:
            # Remove from position-user mapping
            user_positions = await self.redis_client.get_hash(HashSets.POSITION_USER_MAPPINGS.value, user_id) or []
            user_positions = [pos for pos in user_positions if pos != position_id]
            await self.redis_client.set_hash(HashSets.POSITION_USER_MAPPINGS.value, user_id, user_positions)

            # Remove from position-id mapping
            position_ids = await self.redis_client.get_hash(HashSets.POSITION_ID_MAPPINGS.value, identifier) or []
            position_ids = [pos for pos in position_ids if pos != position_id]
            await self.redis_client.set_hash(HashSets.POSITION_ID_MAPPINGS.value, identifier, position_ids)

        except Exception as e:
            logger.error(f"Error removing position mappings: {e}")

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
        