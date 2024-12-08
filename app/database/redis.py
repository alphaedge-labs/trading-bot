import json
import aioredis
from time import sleep
from config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    REDIS_DB
)
from utils.logging import logger
redis_logger = logger.bind(name="redis")

redis_host = REDIS_HOST
redis_port = int(REDIS_PORT) or 6379
redis_password = REDIS_PASSWORD
redis_db = int(REDIS_DB) or 0

class RedisClient:
    def __init__(self, prefix, redis_host, redis_port, redis_password, redis_db, max_retries=20):
        self.prefix = prefix
        self.max_retries = max_retries
        self.client = None  # Will be initialized in connect
        self.redis_params = {
            "host": redis_host,
            "port": redis_port,
            "password": redis_password,
            "db": redis_db
        }
        self.pubsub = None

    async def _connect(self):
        retries = 0
        while retries < self.max_retries:
            try:
                if not self.client:
                    self.client = await aioredis.Redis(**self.redis_params)
                await self.client.ping()
                self.pubsub = self.client.pubsub()
                redis_logger.info("Connected to Redis!!!")
                return
            except (aioredis.ConnectionError, ConnectionRefusedError):
                retries += 1
                redis_logger.info(f"Attempt {retries} to reconnect...")
                sleep(retries * 0.5)
        raise Exception("Too many retries.")

    async def _publish_event(self, category, action, data):
        """Helper method to publish events"""
        event = {
            "category": category,
            "action": action,
            "data": data
        }
        await self.publish(category, json.dumps(event))

    def _generate_key(self, data):
        """Generate a Redis key by joining arguments with colons."""
        if not data:
            raise ValueError("At least one argument is required for key generation")
            
        if any(arg is None for arg in data):
            raise ValueError("None values are not allowed in Redis keys")
        
        #TODO: fix this to fit equity stocks too, rn this is only for options
        return f'{data["symbol"]}:{data["expiry_date"]}:{data["right"]}:{data["strike_price"]}'

    # Set or update a hash
    async def set_hash(self, category, key, data):
        if not key:
            key = self._generate_key(data)
        if isinstance(data, dict) or isinstance(data, list):
            data = json.dumps(data)
        await self.client.hset(category, key, data)

    # Get a hash
    async def get_hash(self, category, identifier):
        data = await self.client.hget(category, identifier)
        return json.loads(data) if data else None

    # Delete a hash
    async def delete_hash(self, category, key):
        await self.client.hdel(category, key)

    # Get all keys in a category
    async def get_all_keys(self, category):
        pattern = self._generate_key(category, "*")
        keys = await self.client.keys(pattern)
        logger.info(f"Retrieved keys for pattern: {pattern}")
        return [key.decode('utf-8') for key in keys]

    # Increment a field in a hash (e.g., quantity)
    async def increment_hash_field(self, category, identifier, field, amount=1):
        key = self._generate_key(category, identifier)
        new_value = await self.client.hincrbyfloat(key, field, amount)
        logger.info(f"Incremented {field} by {amount} for key: {key}")
        # Publish event
        await self._publish_event(category, "update", {
            "identifier": identifier,
            field: new_value
        })

    async def publish(self, channel: str, message: str):
        """Publish a message to a channel"""
        await self.client.publish(channel, message)
        logger.info(f"Published message to channel: {channel}")

    def get_pubsub(self):
        """Get a pubsub instance"""
        return self.pubsub
    
    async def _disconnect(self):
        """Disconnect from Redis"""
        await self.client.close()
        logger.info("Disconnected from Redis")

    def get_new_connection(self):
        """Create and return a new RedisClient instance"""
        new_client = RedisClient(
            prefix=self.prefix,
            redis_host=self.redis_params["host"],
            redis_port=self.redis_params["port"],
            redis_password=self.redis_params["password"],
            redis_db=self.redis_params["db"]
        )
        # Initialize the connection synchronously
        new_client.client = aioredis.Redis(**self.redis_params)
        new_client.pubsub = new_client.client.pubsub()
        return new_client

redis_client = RedisClient(
    prefix='alphaedge',
    redis_host=REDIS_HOST,
    redis_port=REDIS_PORT,
    redis_password=REDIS_PASSWORD,
    redis_db=REDIS_DB
)