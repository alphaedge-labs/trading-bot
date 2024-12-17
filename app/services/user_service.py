from typing import Dict, Optional
from datetime import datetime
from loguru import logger

from database.redis import redis_client
from database.mongodb import db
from constants.collections import Collections

class UserService:
    def __init__(self):
        self.redis_client = redis_client.get_new_connection()
        self.users: Dict[str, dict] = {}
        
    async def initialize(self):
        """Load all active users into memory and Redis"""
        try:
            from database.mongodb import db
            self.users_collection = db[Collections.USERS.value]
            active_users = await self.users_collection.find({"is_active": True}).to_list(length=None)
            for user in active_users:
                user_id = user["_id"]
                self.users[user_id] = user
                # Cache in Redis
                await self.redis_client.set_hash("users", user_id, user)
            logger.info(f"Initialized {len(self.users)} active users")
        except Exception as e:
            logger.error(f"Error initializing users: {e}")
            raise

    async def get_active_users(self) -> Dict[str, dict]:
        """Get all active users"""
        return self.users

    async def get_user(self, user_id: str) -> Optional[dict]:
        """Get user data from Redis (primary) or MongoDB (fallback)"""
        try:
            # Try Redis first
            user = await self.redis_client.get_hash("users", user_id)
            if not user:
                # Fallback to MongoDB
                user = await self.users_collection.find_one({"_id": user_id})
                if user:
                    # Cache in Redis for next time
                    await self.redis_client.set_hash("users", user_id, user)
            return user
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None

    async def can_block_capital(self, user_id: str, amount: float) -> bool:
        user = await self.get_user(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            return False
        
        available_balance = user.get("capital", {}).get("available_balance", 0)
        if available_balance < amount:
            logger.warning(f"Insufficient balance for user {user_id}. Required: {amount}, Available: {available_balance}")
            return False
        return True

    async def block_capital(self, user_id: str, amount: float) -> bool:
        """Block capital for a new position"""
        try:
            user = await self.get_user(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return False

            # Update MongoDB
            result = await self.users_collection.update_one(
                {
                    "_id": user_id,
                    "capital.available_balance": {"$gte": amount}  # Double-check balance
                },
                {
                    "$inc": {
                        "capital.available_balance": -amount,
                        "capital.total_deployed": amount,
                        "risk_management.open_positions": 1
                    },
                    "$push": {
                        "activity_logs": {
                            "timestamp": datetime.now(),
                            "activity": f"Blocked capital: {amount}"
                        }
                    }
                }
            )

            if result.modified_count == 0:
                logger.warning(f"Failed to block capital for user {user_id}")
                return False

            # Update Redis
            user["capital"]["available_balance"] -= amount
            user["capital"]["total_deployed"] += amount
            user["risk_management"]["open_positions"] += 1
            await self.redis_client.set_hash("users", user_id, user)
            
            # Update in-memory
            self.users[user_id] = user

            logger.info(f"Successfully blocked {amount} capital for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error blocking capital for user {user_id}: {e}")
            return False

    async def release_capital(self, user_id: str, amount: float, pnl: float) -> bool:
        """Release blocked capital and update with PnL"""
        try:
            user = await self.get_user(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return False

            # Update MongoDB
            result = await self.users_collection.update_one(
                {"_id": user_id},
                {
                    "$inc": {
                        "capital.available_balance": amount + pnl,
                        "capital.total_deployed": -amount,
                        "risk_management.open_positions": -1
                    },
                    "$push": {
                        "activity_logs": {
                            "timestamp": datetime.now(),
                            "activity": f"Released capital: {amount}, PnL: {pnl}"
                        }
                    }
                }
            )

            if result.modified_count == 0:
                logger.warning(f"Failed to release capital for user {user_id}")
                return False

            # Update Redis
            user["capital"]["available_balance"] += (amount + pnl)
            user["capital"]["total_deployed"] -= amount
            user["risk_management"]["open_positions"] -= 1
            await self.redis_client.set_hash("users", user_id, user)
            
            # Update in-memory
            self.users[user_id] = user

            logger.info(f"Successfully released {amount} capital with PnL {pnl} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error releasing capital for user {user_id}: {e}")
            return False

    async def get_available_capital(self, user_id: str) -> float:
        """Get user's current available capital"""
        try:
            user = await self.get_user(user_id)
            return user.get("capital", {}).get("available_balance", 0) if user else 0
        except Exception as e:
            logger.error(f"Error getting available capital for user {user_id}: {e}")
            return 0

    async def update_user_settings(self, user_id: str, settings: dict) -> bool:
        """Update user settings"""
        try:
            # Update MongoDB
            result = await self.users_collection.update_one(
                {"_id": user_id},
                {"$set": settings}
            )

            if result.modified_count == 0:
                return False

            # Update Redis
            user = await self.get_user(user_id)
            if user:
                user.update(settings)
                await self.redis_client.set_hash("users", user_id, user)
                self.users[user_id] = user

            return True
        except Exception as e:
            logger.error(f"Error updating settings for user {user_id}: {e}")
            return False 