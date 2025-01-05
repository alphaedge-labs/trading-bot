from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from constants.orders import OrderType, TransactionType, Validity, OrderStatus, Variety, Exchange

class Order(BaseModel):
    order_id: str
    user_id: str
    broker: str
    position_id: Optional[str] = None
    
    # Trade details
    symbol: str
    exchange: Exchange
    transaction_type: TransactionType
    quantity: int
    price: float
    order_type: OrderType
    product: str
    variety: Variety
    validity: Validity
    
    # Optional parameters
    trigger_price: Optional[float] = None
    disclosed_quantity: Optional[int] = 0
    
    # Options specific
    strike_price: Optional[float] = None
    expiry_date: Optional[str] = None
    right: Optional[str] = None
    
    # Status and tracking
    status: OrderStatus
    is_exit: bool = False
    capital_to_block: float
    average_price: Optional[float] = None
    filled_quantity: Optional[int] = 0
    pending_quantity: Optional[int] = 0
    
    # Metadata
    created_at: datetime
    updated_at: Optional[datetime] = None
    guid: str
    identifier: str
    
    class Config:
        use_enum_values = True 