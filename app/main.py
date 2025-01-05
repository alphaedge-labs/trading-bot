import sys
import asyncio
import logging

import uvicorn
from loguru import logger
from fastapi import FastAPI
from contextlib import asynccontextmanager
from utils.datetime import get_ist_time

from services.signal_processing_service import SignalProcessingService
from services.trading_service import TradingService
from services.user_service import UserService
from services.order_service import OrderService

from database.mongodb import init_db

from routes.zerodha_kite import router as zerodha_router

from config import PORT

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
    yield

app = FastAPI(lifespan=lifespan, debug=True)

app.include_router(zerodha_router, prefix="/trading/v1/brokers/zerodha")

@app.get("/health")
def health_check():
    return {"status": "running", "message": "AlphaEdge Trading Bot is running", "datetime": get_ist_time()}

async def start_fastapi():
    """Run the FastAPI app in the same event loop."""
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    logger.info(f"Starting FastAPI server on port {PORT}")
    await server.serve()

async def main():
    # Store all services that need cleanup
    services = {}
    
    try:
        await init_db()

        global loop
        loop = asyncio.get_running_loop()

        # Initialize services
        user_service = UserService()
        await user_service.initialize()
        services['user_service'] = user_service

        # Start the FastAPI app
        fastapi_task = asyncio.create_task(start_fastapi())

        trading_service = TradingService(user_service=user_service)
        await trading_service.start()
        services['trading_service'] = trading_service

        order_service = OrderService(user_service=user_service)
        services['order_service'] = order_service

        signal_processing_service = SignalProcessingService(
            user_service=user_service, 
            trading_service=trading_service,
            order_service=order_service
        )
        await signal_processing_service.start()
        services['signal_processing_service'] = signal_processing_service
        
        
        # add services to app state
        app.state.user_service = user_service
        app.state.trading_service = trading_service
        app.state.signal_processing_service = signal_processing_service
        app.state.order_service = order_service

        # Wait indefinitely until interrupted
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.warning("Received keyboard interrupt, initiating shutdown...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
    finally:
        logger.warning("Shutting down services...")
        
        # Cleanup FastAPI
        if 'fastapi_task' in locals():
            fastapi_task.cancel()
            try:
                await fastapi_task
            except asyncio.CancelledError:
                pass

        # Cleanup Redis connections and services
        if 'signal_processing_service' in services:
            logger.info("Stopping signal processing service...")
            await services['signal_processing_service'].stop_listening()
            
        if 'trading_service' in services:
            logger.info("Stopping trading service...")
            await services['trading_service'].stop_listening()

        if 'order_service' in services:  # Add this block
            logger.info("Stopping order service...")
            await services['order_service'].stop()

        # Close Redis connections
        if 'redis_client' in services:
            logger.info("Closing Redis connections...")
            await services['redis_client']._disconnect()

        # Close MongoDB connection (if needed)
        # Add any other cleanup needed

        logger.success("Shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.error("Received keyboard interrupt in main thread")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
