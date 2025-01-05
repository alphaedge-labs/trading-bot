import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from config import (
    MONGO_URI,
    MONGO_DB
)
from utils.logging import logger
from database.manager import DatabaseManager

mongo_logger = logger.bind(name="mongodb")

class AsyncMongoDBClient:
    def __init__(self, db_name, max_retries=20):
        self.db_name = db_name
        self.max_retries = max_retries
        self.client = AsyncIOMotorClient(MONGO_URI)
        self._is_connected = False

    async def ensure_connected(self):
        if not self._is_connected:
            await self._connect()
            self._is_connected = True

    async def _connect(self):
        retries = 0
        while retries < self.max_retries:
            try:
                await self.client.admin.command('ping')
                mongo_logger.success("Connected to MongoDB!!!")
                return
            except ConnectionFailure:
                retries += 1
                mongo_logger.warning(f"Attempt {retries} to reconnect...")
                await asyncio.sleep(retries * 0.5)
        raise Exception("Too many retries.")

    async def get_database(self):
        await self.ensure_connected()
        return self.client[self.db_name]

# Create the client instance
mongo_client = AsyncMongoDBClient(db_name=MONGO_DB)

# Initializing db needs to be done in an async context
db = None

# Initialize database connection asynchronously
async def init_db():
    db = await mongo_client.get_database()
    DatabaseManager.set_db(db)
    logger.success("Database initialized and set in DatabaseManager")
    return db
