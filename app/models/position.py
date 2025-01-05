from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from constants.positions import PositionStatus, PositionType

class Position(BaseModel):
    position_id: str
    user_id: str
    broker: str
    entry_order_id: str
    exit_order_id: Optional[str] = None
    
    # Trade details
    symbol: str
    position_type: PositionType
    quantity: int
    entry_price: float
    current_price: float
    
    # Risk management
    stop_loss: float
    take_profit: float
    blocked_capital: float
    
    # P&L tracking
    unrealized_pnl: float = 0
    realized_pnl: float = 0
    
    # Options specific
    strike_price: Optional[float] = None
    expiry_date: Optional[str] = None
    right: Optional[str] = None
    
    # Status and metadata
    status: PositionStatus
    should_exit: bool = False
    identifier: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None

    class Config:
        use_enum_values = True 