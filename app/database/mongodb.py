import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from config import (
    MONGO_URI,
    MONGO_DB
)
from utils.logging import logger

mongo_logger = logger.bind(name="mongodb")

class AsyncMongoDBClient:
    def __init__(self, db_name, max_retries=20):
        self.db_name = db_name
        self.max_retries = max_retries
        self.client = AsyncIOMotorClient(MONGO_URI)
        asyncio.create_task(self._connect())

    async def _connect(self):
        retries = 0
        while retries < self.max_retries:
            try:
                await self.client.admin.command('ping')
                mongo_logger.info("Connected to MongoDB!!!")
                return
            except ConnectionFailure:
                retries += 1
                mongo_logger.info(f"Attempt {retries} to reconnect...")
                await asyncio.sleep(retries * 0.5)
        raise Exception("Too many retries.")

    def get_database(self):
        return self.client[self.db_name]

mongo_client = AsyncMongoDBClient(db_name=MONGO_DB)
db = mongo_client.get_database()
