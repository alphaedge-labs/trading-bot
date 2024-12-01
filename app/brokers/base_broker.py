from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseBroker(ABC):
    @abstractmethod
    def get_open_positions(self):
        pass

    @abstractmethod
    def get_closed_positions(self):
        pass

    @abstractmethod
    def get_open_orders(self):
        pass

    @abstractmethod
    def get_order_history(self):
        pass

    @abstractmethod
    def get_account_details(self):
        pass

    @abstractmethod
    def get_required_margin(self, order: Dict[str, Any]):
        pass

    @abstractmethod
    def cancel_order(self, order_id: str):
        pass
