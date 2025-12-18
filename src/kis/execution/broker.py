"""Broker client interface and Spy implementation for testing"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BrokerClient(ABC):
    """Abstract broker client interface"""
    
    @abstractmethod
    async def place_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place order with broker.
        
        Args:
            order_data: Order data dictionary
            
        Returns:
            Broker response dictionary
        """
        pass


class SpyBrokerClient(BrokerClient):
    """Spy broker client for testing - tracks call count"""
    
    def __init__(self):
        """Initialize spy broker client"""
        self.call_count = 0
        self.last_order_data = None
        self.call_history = []
    
    async def place_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place order (mock implementation for testing).
        
        Args:
            order_data: Order data dictionary
            
        Returns:
            Mock broker response
        """
        self.call_count += 1
        self.last_order_data = order_data
        self.call_history.append(order_data)
        
        # Return mock response
        return {
            "broker_order_id": f"mock-order-{self.call_count}",
            "status": "pending",
            "message": "Order placed (mock)"
        }
    
    def reset(self):
        """Reset call count and history"""
        self.call_count = 0
        self.last_order_data = None
        self.call_history = []

