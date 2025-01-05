from enum import Enum

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    SL_MARKET = "SL_MARKET"

class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"

class Validity(Enum):
    DAY = "DAY"
    GTD = "GTD"
    IOC = "IOC"
    GTC = "GTC"
    TTL = "TTL"

class OrderStatus(Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    OPEN = "OPEN"

class Variety(Enum):
    REGULAR = "regular"
    BO = "bo"
    CO = "co"
    AMO = "amo"
    MARGIN = "margin"

class Exchange(Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"
    CDS = "CDS"
    BFO = "BFO"
    MCX = "MCX"
    BCD = "BCD"

class Product(Enum):
    MIS = "MIS"
    INTRADAY = "INTRADAY"
    MARGIN = "MARGIN"
    AMO = "AMO"