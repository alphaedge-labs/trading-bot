import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from database.redis import RedisClient
from database.mongodb import AsyncMongoDBClient

@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def mock_redis():
    redis_client = MagicMock(spec=RedisClient)
    redis_client._connect = AsyncMock()
    redis_client.publish = AsyncMock()
    redis_client.set_hash = AsyncMock()
    redis_client.get_hash = AsyncMock()
    redis_client.delete_hash = AsyncMock()
    redis_client.get_all_keys = AsyncMock()
    return redis_client

@pytest.fixture
async def mock_mongodb():
    mongo_client = MagicMock(spec=AsyncMongoDBClient)
    mongo_client._connect = AsyncMock()
    mongo_client.get_database = AsyncMock()
    return mongo_client 