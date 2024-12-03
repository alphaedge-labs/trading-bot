from brokers.base_broker import BaseBroker
from typing import Dict, Any

class PaperBroker(BaseBroker):
    def __init__(self):
        pass
    
    def get_open_positions(self):
        pass

    def get_closed_positions(self):
        pass

    def get_open_orders(self):
        pass

    def get_order_history(self):
        pass

    def get_account_details(self):
        pass

    def get_required_margin(self, order: Dict[str, Any]):
        pass
