import asyncio
from loguru import logger
from typing import Optional, Dict
from app.database.redis import redis_client
from app.database.mongodb import db
from app.brokers.kotak_neo import KotakNeo
from app.models.user import User

class TradingService:
    def __init__(self):
        self.redis = redis_client
        self.running = False
        self._trading_task: Optional[asyncio.Task] = None
        self.users: Dict[str, Dict] = {}  # Store user configs and broker instances
        
    async def start(self):
        """Start the trading service"""
        if self.running:
            logger.warning("Trading service is already running")
            return
            
        # Load all users from MongoDB
        await self._load_users()
        
        self.running = True
        self._trading_task = asyncio.create_task(self._trading_loop())
        logger.info("Trading service started")

    async def _load_users(self):
        """Load all active users from MongoDB and initialize their data in Redis"""
        try:
            users_collection = db['users']
            async for user_data in users_collection.find({"trading_config.is_active": True}):
                user = User(**user_data)
                
                # Initialize broker instance for user
                if user.broker_name == "kotak_neo":
                    broker = KotakNeo(
                        client_id=user.broker_credentials["client_id"],
                        client_secret=user.broker_credentials["client_secret"]
                    )
                    # Add more broker types as needed
                
                # Store user config and broker instance
                self.users[user.user_id] = {
                    "config": user.trading_config,
                    "broker": broker
                }
                
                # Initialize user data in Redis
                self.redis.set_hash("users", user.user_id, {
                    "max_capital": str(user.trading_config.max_capital),
                    "used_capital": "0",
                    "max_risk_per_trade": str(user.trading_config.max_risk_per_trade),
                    "risk_reward_ratio": str(user.trading_config.risk_reward_ratio),
                    "active_positions": "0"
                })
                
                logger.info(f"Loaded user {user.user_id} into trading service")
                
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            raise

    async def _trading_loop(self):
        """Main trading loop"""
        while self.running:
            try:
                # Process signals for all users
                await self._process_signals()
                # Monitor positions for all users
                await self._monitor_all_positions()
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(5)

    async def _process_signals(self):
        """Process trading signals for all users"""
        signals = self.redis.get_all_keys("signals")
        for signal_key in signals:
            signal_data = self.redis.get_hash("signals", signal_key.split(":")[-1])
            if signal_data.get("processed") != "true":
                # Process signal for each eligible user
                await self._process_signal_for_users(signal_data)

    async def _process_signal_for_users(self, signal_data: dict):
        """Process a signal for all eligible users"""
        for user_id, user_info in self.users.items():
            try:
                # Check if user can take this trade
                if await self._can_take_trade(user_id, signal_data):
                    await self._execute_trade(user_id, user_info, signal_data)
            except Exception as e:
                logger.error(f"Error processing signal for user {user_id}: {e}")

    async def _can_take_trade(self, user_id: str, signal_data: dict) -> bool:
        """Check if user can take this trade based on their configuration"""
        user_data = self.redis.get_hash("users", user_id)
        max_capital = float(user_data["max_capital"])
        used_capital = float(user_data["used_capital"])
        max_risk = float(user_data["max_risk_per_trade"])

        # Add your trade validation logic here
        # Example:
        if used_capital + float(signal_data["required_capital"]) > max_capital:
            return False
        if float(signal_data["risk_amount"]) > max_risk:
            return False
        return True

    async def _execute_trade(self, user_id: str, user_info: dict, signal_data: dict):
        """Execute trade for a specific user"""
        try:
            broker = user_info["broker"]
            config = user_info["config"]

            # Create order based on signal
            order_response = await self._create_order(broker, signal_data, config)

            # Update Redis with position information
            self.redis.set_hash(f"positions:{user_id}", signal_data["identifier"], {
                "entry_price": str(order_response["price"]),
                "quantity": str(order_response["quantity"]),
                "stop_loss": str(signal_data["stop_loss"]),
                "target": str(signal_data["target"]),
                "status": "active"
            })

            # Update user's used capital
            self.redis.increment_hash_field("users", user_id, "used_capital", 
                                         float(signal_data["required_capital"]))
            self.redis.increment_hash_field("users", user_id, "active_positions", 1)

        except Exception as e:
            logger.error(f"Error executing trade for user {user_id}: {e}")

    async def _monitor_all_positions(self):
        """Monitor positions for all users"""
        for user_id, user_info in self.users.items():
            try:
                positions = self.redis.get_all_keys(f"positions:{user_id}")
                for position_key in positions:
                    position_data = self.redis.get_hash(f"positions:{user_id}", 
                                                      position_key.split(":")[-1])
                    if position_data["status"] == "active":
                        await self._check_position_exit(user_id, user_info["broker"], 
                                                      position_data)
            except Exception as e:
                logger.error(f"Error monitoring positions for user {user_id}: {e}")

    async def _check_position_exit(self, user_id: str, broker: KotakNeo, position: dict):
        """Check if position needs to be exited for a specific user"""
        try:
            # Implement your position exit logic here
            # Example: Check if stop loss or target is hit
            current_price = await self._get_current_price(broker, position["symbol"])
            
            if (float(current_price) <= float(position["stop_loss"]) or 
                float(current_price) >= float(position["target"])):
                
                # Exit position
                await self._exit_position(user_id, broker, position)
                
        except Exception as e:
            logger.error(f"Error checking position exit for user {user_id}: {e}") 