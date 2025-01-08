import asyncio
import json
from typing import Dict
from datetime import datetime

from utils.logging import logger

from database.redis import redis_client
from database.mongodb import AsyncMongoDBClient
from database.manager import DatabaseManager

from constants.redis import HashSets, Channels
from constants.collections import Collections
from constants.orders import OrderStatus

from services.user_service import UserService
from utils.id_generator import generate_id

class OrderService:
    def __init__(self, user_service: UserService):
        self.running = False
        self.active_users = set()  # Store active user IDs
        self.redis_client = redis_client.get_new_connection()
        self.user_service = user_service
        self.channels = [Channels.ZERODHA_ORDERS.value]
        self.db_manager = DatabaseManager()
        self.db: AsyncMongoDBClient = None

    async def start(self):
        """Start listening to Redis channels"""
        self.running = True
        self.pubsub = self.redis_client.pubsub
        await self.pubsub.subscribe(*self.channels)
        logger.info(f"Started listening to channels: {self.channels}")

        # Wait for database to initialize
        self.db = await self.db_manager.get_db()

        while self.running:
            try:
                message = await self.pubsub.get_message()

                if message and message['type'] == 'message':
                    channel = message['channel'].decode('utf-8')
                    data = json.loads(message['data'])

                    if channel == Channels.ZERODHA_ORDERS.value:
                        user_id = data.get('user_id')
                        request_id = data.get('request_id')

                        if request_id:
                            hashset_name = f"{HashSets.ZERODHA_UPDATES.value}_{user_id}"
                            order_update = await self.redis_client.get_hash(hashset_name, request_id)
                            if order_update:
                                logger.info(f'Processing order update: {order_update}')
                                await self._process_order_update(
                                    user_id, 
                                    order_update
                                )
                                await self.redis_client.delete_hash(hashset_name, request_id)
                        
                    logger.debug(f"Received event from channel '{channel}': {data}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding message: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await asyncio.sleep(1)
                continue

        # await asyncio.sleep(0.1) # Preventing CPU overload, for pussies

    async def _process_order_update(self, user_id: str, order_data: Dict):
        """Process an order update message"""
        try:
            order_id = order_data.get('order_id')
            status = order_data.get('status')

            if not order_id or not status:
                logger.error("Missing order_id or status in order update")
                return

            # Verify collection exists
            collection = self.db[Collections.ORDERS.value]
            await collection.update_one(
                {"order_id": order_id},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.now()
                    }
                }
            )

            if status == OrderStatus.COMPLETED.value:
                # Check if this is an entry or exit order
                order = await collection.find_one({"order_id": order_id})
                
                if not order:
                    logger.error(f"Order not found: {order_id}")
                    return

                position_id = order.get('position_id')

                if order.get('is_exit'):
                    await self._close_position(position_id, user_id, order_data)
                else:
                    # Create/Update position in Redis
                    await self._create_or_update_position(position_id, user_id, order)

            elif status in [OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value]:
                # Handle cancelled/rejected orders
                logger.warning(f"Order {order_id} {status.lower()}")
                # Add logic here to release capital from user
                order = await self.db[Collections.ORDERS.value].find_one({"order_id": order_id})
                
                if order:
                    remark = f"Released capital for order {order_id} {status.lower()} by user {user_id}"
                    await self.user_service.release_capital(user_id, order.get("capital_to_block"), 0, remark)
    
        except Exception as e:
            logger.error(f"Error processing order update: {e}")

    async def _close_position(self, position_id: str, user_id: str, order_data: Dict):
        """Close a position in Redis"""
        try:
            # Get position data
            position = await self.redis_client.get_hash(HashSets.POSITIONS.value, position_id)
            
            if not position:
                logger.error(f"Position not found: {position_id}")
                return

            logger.success(f'order_data: {order_data}')
            logger.success(f'position: {position}')

            # Calculate final P&L
            exit_price = float(order_data.get('average_price', 0))
            
            pnl = float(position.get("unrealized_pnl"))
            if position.get('position_type') == 'SHORT':
                pnl = -pnl

            # Update position with final status
            position.update({
                'status': 'CLOSED',
                'exit_price': exit_price,
                'unrealized_pnl': 0,
                'realized_pnl': pnl,
                'closed_at': datetime.now(),
                "created_at": datetime.strptime(position.get("created_at"), "%a %b  %d %H:%M:%S %Y"),
                "last_updated": datetime.strptime(position.get("last_updated"), "%a %b  %d %H:%M:%S %Y"),
                "timestamp": datetime.strptime(position.get("timestamp"), "%Y-%m-%dT%H:%M:%S.%f")
            })

            await self.db[Collections.CLOSED_POSITIONS.value].insert_one(position)
            # Release blocked capital and update capital with realized PnL

            logger.info(f'Storing closed position in db: {position}')

            await self.user_service.release_capital(
                user_id=position.get("user_id"),
                amount=position.get("blocked_capital"),
                pnl=pnl
            )

            identifier = self.redis_client._generate_key(position)
            await asyncio.gather(
                # Remove from positions hash
                self.redis_client.delete_hash(HashSets.POSITIONS.value, position_id),
                # Clean up position ID mapping
                self._cleanup_mapping(HashSets.POSITION_ID_MAPPINGS, identifier, position_id),
                # Clean up position user mapping
                self._cleanup_mapping(HashSets.POSITION_USER_MAPPINGS, position["user_id"], position_id)
            )
            logger.success(f'Cleared all mappings for {position_id}')

        except Exception as e:
            logger.error(f"Error closing position: {e}")

    async def _create_or_update_position(self, position_id: str, user_id: str, order: Dict):
        """Create or update a position in Redis"""
        try:
            if not position_id:
                # Create position data
                position_id = f'pos_{generate_id()}'

                position_data = {
                    "entry_order_id": order["order_id"],
                    "position_id": position_id,
                    "user_id": str(order["user_id"]),
                    "symbol": str(order["symbol"]),
                    "right": str(order["right"]),
                    "strike_price": str(order["strike_price"]),
                    "expiry_date": str(order["expiry_date"]),
                    "identifier": str(order.get("identifier")),
                    "broker": str(order["broker"]),
                    "position_type": str(order.get("position_type", "LONG")),
                    "quantity": order["quantity"],
                    "entry_price": order["entry_price"],
                    "current_price": order["entry_price"],
                    "unrealized_pnl": 0,
                    "realized_pnl": 0,
                    "stop_loss": order["stop_loss"],
                    "take_profit": order["target"],
                    "timestamp": datetime.now().isoformat(),
                    "status": "OPEN",
                    "should_exit": False,
                    "blocked_capital": order.get("capital_to_block"),
                    "last_updated": datetime.now().strftime("%c"),
                    "created_at": datetime.now().strftime("%c")
                }
                    
                # Set position data, update position mapping and user mapping concurrently
                await asyncio.gather(
                    self.redis_client.set_hash(HashSets.POSITIONS.value, position_id, position_data),
                    self._update_position_mapping(order.get("identifier"), position_id),
                    self._update_position_user_mapping(order["user_id"], position_id),
                    self._update_order_with_position_id(order["order_id"], position_id)
                )

                logger.success(f'Position {position_id} set in memory')
            else:
                logger.warning(f"Position {position_id} already exists")

        except Exception as e:
            logger.error(f"Error creating/updating position: {e}")

    async def _update_order_with_position_id(self, order_id: str, position_id: str):
        """Update order with position_id"""
        await self.db[Collections.ORDERS.value].update_one(
            {"order_id": order_id},
            {"$set": {"position_id": position_id}}
        )

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

    async def stop(self):
        """Stop the order service"""
        self.running = False
        logger.info("Order service stopped")