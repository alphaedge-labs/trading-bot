from enum import Enum

class PositionStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    EXIT_FAILED = "EXIT_FAILED"

class PositionType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"