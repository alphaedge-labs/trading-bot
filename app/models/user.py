from pydantic import BaseModel
from typing import Optional, Dict

class TradingConfig(BaseModel):
    risk_reward_ratio: float = 2.0
    max_capital: float
    max_risk_per_trade: float
    allowed_symbols: list[str] = []
    is_active: bool = True

class User(BaseModel):
    user_id: str
    broker_id: str
    broker_name: str  # e.g., "kotak_neo"
    trading_config: TradingConfig
    broker_credentials: Dict[str, str]  # Store encrypted credentials
