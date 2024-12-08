from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseBroker(ABC):
    @abstractmethod
    def get_open_positions(self):
        """Get all open positions"""
        pass

    @abstractmethod
    def get_closed_positions(self):
        """Get all closed positions"""
        pass

    @abstractmethod
    def get_open_orders(self):
        """Get all open orders"""
        pass

    @abstractmethod
    def get_order_history(self):
        """Get order history"""
        pass

    @abstractmethod
    def get_account_details(self):
        """Get account details"""
        pass

    @abstractmethod
    def get_required_margin(self, order: Dict[str, Any]):
        """Get required margin for an order"""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str):
        """Cancel an order"""
        pass

    @abstractmethod
    def form_order(self, data: Dict[str, Any], is_exit: bool):
        """Form an order"""
        pass

    @abstractmethod
    def place_order(self, order: Dict[str, Any]):
        """Place an order"""
        pass