from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class StreamerConfig(BaseModel):
    STREAMER_BROKER: str
    STREAMER_APP_KEY: str = ""
    STREAMER_SECRET_KEY: str = ""
    STREAMER_SESSION_TOKEN: str = ""

class TradingConfig(BaseModel):
    TRADING_BROKER: str
    TRADING_APP_KEY: str = ""
    TRADING_SECRET_KEY: str = ""
    TRADING_FIN_KEY: str = ""
    TRADING_CLIENT_ID: str = ""
    TRADING_PASSWORD: str = ""
    TRADING_SESSION_TOKEN: str = ""

class RiskManagement(BaseModel):
    ideal_risk_reward_ratio: float = Field(default=2.5, description="Recommended range is typically 2 or above")
    max_drawdown_percentage: float = Field(default=10, description="Maximum loss from peak capital as percentage")
    stop_loss_buffer: float = Field(default=0.5, description="Percentage or points buffer for stop loss")
    position_sizing_method: str = Field(default="fixed", description="Options: fixed, percentage_of_capital")
    max_open_positions: int = Field(default=5, description="Limit on the number of active trades")
    open_positions: int = Field(default=0, description="Number of open positions")

class Capital(BaseModel):
    total_deployed: float
    available_balance: float

class TradingHours(BaseModel):
    start: str
    end: str

class Settings(BaseModel):
    preferred_trading_hours: TradingHours
    trade_frequency: str
    preferred_instruments: List[str]

class ActivityLog(BaseModel):
    timestamp: datetime
    activity: str

class Notifications(BaseModel):
    email: bool = True
    sms: bool = False
    push: bool = True

class Preferences(BaseModel):
    notifications: Notifications
    language: str = "en"

class User(BaseModel):
    _id: str
    is_admin: bool = False
    is_active: bool = True
    streamer: StreamerConfig
    trading: List[TradingConfig]
    active_brokers: List[str]
    name: str
    last_login: datetime
    risk_management: RiskManagement
    capital: Capital
    settings: Settings
    activity_logs: List[ActivityLog]
    preferences: Preferences

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }