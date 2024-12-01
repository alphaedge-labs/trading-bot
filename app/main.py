import sys
import uvicorn
from fastapi import FastAPI
import logging
from contextlib import asynccontextmanager
from loguru import logger

from app.utils.datetime import get_ist_time
from app.services.trading_service import TradingService

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
)
logger.add(
    "./app.log",  # File path for logging
    rotation="500 MB",  # Rotate when file reaches 500MB
    retention="10 days",  # Keep logs for 10 days
    compression="zip",  # Compress rotated logs
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO"
)

# Intercept uvicorn's default logger
class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# Setup intercept handler for uvicorn
logging.getLogger("uvicorn").handlers = [InterceptHandler()]
logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize trading service
    trading_service = TradingService()
    # Start trading service
    await trading_service.start()
    # Store trading service in app state
    app.state.trading_service = trading_service
    yield
    # Cleanup: Stop trading service
    await trading_service.stop()

app = FastAPI(lifespan=lifespan, debug=True)

@app.get("/health")
def health_check():
    return {"status": "running", "message": "AlphaEdge Trading Bot is running", "datetime": get_ist_time()}

if __name__ == "__main__":
    from app.config import PORT
    uvicorn.run(app, host="0.0.0.0", port=PORT)