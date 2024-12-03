from loguru import logger

logger.add("alphaedge__trading_bot.log", rotation="50 MB", retention="10 days", compression="zip", format="{time} {level} {message}", backtrace=True, diagnose=True)