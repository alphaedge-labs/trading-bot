from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger

class DatabaseManager:
    _instance = None
    _db: Optional[AsyncIOMotorDatabase] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def get_db(cls) -> Optional[AsyncIOMotorDatabase]:
        # No need to await here since we're just returning the stored db instance
        if cls._db is None:
            raise RuntimeError("Database not initialized. Call set_db first.")
        return cls._db


    @classmethod
    def set_db(cls, db: AsyncIOMotorDatabase):
        cls._db = db
        logger.info("Database connection set in DatabaseManager")

    @classmethod
    def ensure_db(cls) -> AsyncIOMotorDatabase:
        if not cls._db:
            raise RuntimeError("Database not initialized. Call set_db first.")
        return cls._db

    @classmethod
    async def check_connection(cls) -> bool:
        """Check if database connection is healthy"""
        if not cls._db:
            return False
        try:
            await cls._db.command('ping')
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False

    @classmethod
    async def reconnect(cls):
        """Attempt to reconnect to database"""
        from database.mongodb import init_db
        try:
            await init_db()
            return True
        except Exception as e:
            logger.error(f"Database reconnection failed: {e}")
            return False 