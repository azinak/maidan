"""المخزون: استلام الكميات وحجزها للطلبات."""

from __future__ import annotations


class OutOfStock(Exception):
    def __init__(self, sku: str, requested: int, available: int) -> None:
        super().__init__(f"الكمية غير كافية من {sku}: المطلوب {requested} والمتاح {available}")
        self.sku = sku
        self.requested = requested
        self.available = available


class Inventory:
    def __init__(self) -> None:
        self._stock: dict[str, int] = {}

    def receive(self, sku: str, qty: int) -> None:
        if qty <= 0:
            raise ValueError("الكمية المستلمة يجب أن تكون موجبة")
        self._stock[sku] = self._stock.get(sku, 0) + qty

    def available(self, sku: str) -> int:
        return self._stock.get(sku, 0)

    def reserve(self, lines: list[tuple[str, int]]) -> None:
        """يحجز كميات طلب كامل دفعة واحدة: إما أن تُحجز كل السطور أو لا شيء."""
        for sku, qty in lines:
            if self.available(sku) < qty:
                raise OutOfStock(sku, qty, self.available(sku))
        for sku, qty in lines:
            self._stock[sku] = self.available(sku) - qty

    def release(self, lines: list[tuple[str, int]]) -> None:
        """يعيد كميات طلب ملغى إلى المخزون."""
        for sku, qty in lines:
            self._stock[sku] = self.available(sku) + qty
