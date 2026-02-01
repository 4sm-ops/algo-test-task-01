#!/usr/bin/env python3
"""
Order Book implementation for B3 market data.

Reconstructs order book from Order_MBO_50 and DeleteOrder_MBO_51 messages.
Maintains top-of-book (best bid/ask) for each security.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import heapq


@dataclass
class Order:
    """Single order in the book."""
    order_id: int
    price: float
    size: int
    side: str  # 'BID' or 'OFFER'
    timestamp_ns: int


@dataclass
class OrderBookLevel:
    """Single price level in the order book."""
    price: float
    total_size: int
    order_count: int


@dataclass
class TopOfBook:
    """Top of book snapshot."""
    timestamp_ns: int
    security_id: int
    symbol: str
    best_bid_price: Optional[float] = None
    best_bid_size: int = 0
    best_ask_price: Optional[float] = None
    best_ask_size: int = 0
    spread: Optional[float] = None
    mid_price: Optional[float] = None


class OrderBook:
    """
    Order book for a single security.

    Maintains bid and ask sides, supports add/modify/delete operations.
    Provides top-of-book (best bid/ask) queries.
    """

    def __init__(self, security_id: int, symbol: str):
        self.security_id = security_id
        self.symbol = symbol

        # Orders indexed by order_id
        self.orders: Dict[int, Order] = {}

        # Price levels: price -> {order_id: size}
        self.bid_levels: Dict[float, Dict[int, int]] = defaultdict(dict)
        self.ask_levels: Dict[float, Dict[int, int]] = defaultdict(dict)

        # Sorted price lists for quick top-of-book
        self._bid_prices: List[float] = []  # max-heap (negated)
        self._ask_prices: List[float] = []  # min-heap

        self.last_update_ns: int = 0

    def add_order(self, order_id: int, price: float, size: int,
                  side: str, timestamp_ns: int) -> None:
        """Add a new order to the book."""
        if order_id in self.orders:
            # Order already exists, treat as modify
            self.modify_order(order_id, price, size, timestamp_ns)
            return

        order = Order(
            order_id=order_id,
            price=price,
            size=size,
            side=side,
            timestamp_ns=timestamp_ns
        )
        self.orders[order_id] = order
        self.last_update_ns = timestamp_ns

        if side == 'BID':
            if price not in self.bid_levels or not self.bid_levels[price]:
                heapq.heappush(self._bid_prices, -price)  # max-heap
            self.bid_levels[price][order_id] = size
        else:  # OFFER
            if price not in self.ask_levels or not self.ask_levels[price]:
                heapq.heappush(self._ask_prices, price)  # min-heap
            self.ask_levels[price][order_id] = size

    def delete_order(self, order_id: int, timestamp_ns: int) -> None:
        """Delete an order from the book."""
        if order_id not in self.orders:
            return

        order = self.orders[order_id]
        self.last_update_ns = timestamp_ns

        if order.side == 'BID':
            if order.price in self.bid_levels:
                self.bid_levels[order.price].pop(order_id, None)
        else:
            if order.price in self.ask_levels:
                self.ask_levels[order.price].pop(order_id, None)

        del self.orders[order_id]

    def modify_order(self, order_id: int, new_price: float,
                     new_size: int, timestamp_ns: int) -> None:
        """Modify an existing order."""
        if order_id not in self.orders:
            return

        order = self.orders[order_id]
        old_price = order.price
        self.last_update_ns = timestamp_ns

        # Remove from old price level
        if order.side == 'BID':
            if old_price in self.bid_levels:
                self.bid_levels[old_price].pop(order_id, None)
            # Add to new price level
            if new_price not in self.bid_levels or not self.bid_levels[new_price]:
                heapq.heappush(self._bid_prices, -new_price)
            self.bid_levels[new_price][order_id] = new_size
        else:
            if old_price in self.ask_levels:
                self.ask_levels[old_price].pop(order_id, None)
            if new_price not in self.ask_levels or not self.ask_levels[new_price]:
                heapq.heappush(self._ask_prices, new_price)
            self.ask_levels[new_price][order_id] = new_size

        # Update order
        order.price = new_price
        order.size = new_size
        order.timestamp_ns = timestamp_ns

    def get_best_bid(self) -> Tuple[Optional[float], int]:
        """Get best bid price and total size at that level."""
        # Clean up empty levels
        while self._bid_prices:
            price = -self._bid_prices[0]
            if price in self.bid_levels and self.bid_levels[price]:
                total_size = sum(self.bid_levels[price].values())
                return price, total_size
            heapq.heappop(self._bid_prices)
        return None, 0

    def get_best_ask(self) -> Tuple[Optional[float], int]:
        """Get best ask price and total size at that level."""
        while self._ask_prices:
            price = self._ask_prices[0]
            if price in self.ask_levels and self.ask_levels[price]:
                total_size = sum(self.ask_levels[price].values())
                return price, total_size
            heapq.heappop(self._ask_prices)
        return None, 0

    def get_top_of_book(self) -> TopOfBook:
        """Get current top of book snapshot."""
        best_bid, bid_size = self.get_best_bid()
        best_ask, ask_size = self.get_best_ask()

        spread = None
        mid_price = None
        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid
            mid_price = (best_bid + best_ask) / 2

        return TopOfBook(
            timestamp_ns=self.last_update_ns,
            security_id=self.security_id,
            symbol=self.symbol,
            best_bid_price=best_bid,
            best_bid_size=bid_size,
            best_ask_price=best_ask,
            best_ask_size=ask_size,
            spread=spread,
            mid_price=mid_price
        )

    def get_depth(self, levels: int = 5) -> Dict[str, List[OrderBookLevel]]:
        """Get order book depth (multiple price levels)."""
        bids = []
        asks = []

        # Get top N bid levels
        bid_prices_sorted = sorted(
            [p for p in self.bid_levels if self.bid_levels[p]],
            reverse=True
        )[:levels]
        for price in bid_prices_sorted:
            total_size = sum(self.bid_levels[price].values())
            order_count = len(self.bid_levels[price])
            bids.append(OrderBookLevel(price, total_size, order_count))

        # Get top N ask levels
        ask_prices_sorted = sorted(
            [p for p in self.ask_levels if self.ask_levels[p]]
        )[:levels]
        for price in ask_prices_sorted:
            total_size = sum(self.ask_levels[price].values())
            order_count = len(self.ask_levels[price])
            asks.append(OrderBookLevel(price, total_size, order_count))

        return {'bids': bids, 'asks': asks}


class OrderBookManager:
    """
    Manages order books for multiple securities.

    Processes Order_MBO and DeleteOrder_MBO messages to maintain
    order books and generate top-of-book snapshots.
    """

    def __init__(self):
        self.books: Dict[int, OrderBook] = {}
        self.tob_history: List[TopOfBook] = []

    def get_or_create_book(self, security_id: int, symbol: str) -> OrderBook:
        """Get existing order book or create new one."""
        if security_id not in self.books:
            self.books[security_id] = OrderBook(security_id, symbol)
        return self.books[security_id]

    def process_order(self, security_id: int, symbol: str, order_id: int,
                      action: str, side: str, price: float, size: int,
                      timestamp_ns: int) -> Optional[TopOfBook]:
        """
        Process an order update message.

        Args:
            security_id: Security identifier
            symbol: Security symbol
            order_id: Unique order identifier
            action: 'NEW', 'CHANGE', or 'DELETE'
            side: 'BID' or 'OFFER'
            price: Order price
            size: Order size
            timestamp_ns: Timestamp in nanoseconds

        Returns:
            TopOfBook snapshot after the update (if top changed)
        """
        book = self.get_or_create_book(security_id, symbol)

        # Get top before update
        old_tob = book.get_top_of_book()

        # Apply update
        if action == 'NEW':
            book.add_order(order_id, price, size, side, timestamp_ns)
        elif action == 'CHANGE':
            book.modify_order(order_id, price, size, timestamp_ns)
        elif action == 'DELETE':
            book.delete_order(order_id, timestamp_ns)

        # Get top after update
        new_tob = book.get_top_of_book()

        # Check if top of book changed
        if (old_tob.best_bid_price != new_tob.best_bid_price or
            old_tob.best_ask_price != new_tob.best_ask_price):
            self.tob_history.append(new_tob)
            return new_tob

        return None

    def get_all_tob(self) -> List[TopOfBook]:
        """Get all top-of-book snapshots."""
        return self.tob_history

    def get_current_tob(self, security_id: int) -> Optional[TopOfBook]:
        """Get current top of book for a security."""
        if security_id in self.books:
            return self.books[security_id].get_top_of_book()
        return None
