from time import sleep
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from app.config import (
    MONGO_URI,
    MONGO_DB
)
from loguru import logger

mongo_logger = logger.bind(name="MongoDB")

class MongoDBClient:
    def __init__(self, db_name, max_retries=20):
        self.db_name = db_name
        self.max_retries = max_retries
        self.client = MongoClient(MONGO_URI)
        self._connect()

    def _connect(self):
        retries = 0
        while retries < self.max_retries:
            try:
                self.client.admin.command('ping')
                mongo_logger.info("Connected to MongoDB!!!")
                return
            except ConnectionFailure:
                retries += 1
                mongo_logger.info(f"Attempt {retries} to reconnect...")
                sleep(retries * 0.5)
        raise Exception("Too many retries.")

    def get_database(self):
        return self.client[self.db_name]

mongo_client = MongoDBClient(db_name=MONGO_DB)
db = mongo_client.get_database()
