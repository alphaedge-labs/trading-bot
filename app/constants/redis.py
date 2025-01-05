from enum import Enum

class HashSets(Enum):
    POSITIONS = "positions"
    POSITION_ID_MAPPINGS = "position_id_mappings"
    POSITION_USER_MAPPINGS = "position_user_mappings"
    USER_ID_MAPPINGS = "user_id_mappings"
    INSTRUMENTS = "instruments"

    # Paper broker specific
    ORDER_ID_MAPPING = "order_id_mapping"
    ORDERS_PENDING = "orders_pending"

    # Zerodha updates
    ZERODHA_UPDATES = 'zerodha_updates'

class Channels(Enum):
    ZERODHA_ORDERS = 'zerodha_orders'