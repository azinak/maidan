"""الطلبات والفواتير."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from makhzan.catalog import Product
from makhzan.money import ZERO, Money

VAT_RATE = Decimal("0.15")


@dataclass
class OrderLine:
    product: Product
    qty: int

    def subtotal(self) -> Money:
        return self.product.price * self.qty


@dataclass
class Order:
    lines: list[OrderLine] = field(default_factory=list)
    status: str = "draft"

    def add(self, product: Product, qty: int = 1) -> None:
        if qty <= 0:
            raise ValueError("الكمية يجب أن تكون موجبة")
        for line in self.lines:
            if line.product.sku == product.sku:
                line.qty += qty
                return
        self.lines.append(OrderLine(product, qty))

    def subtotal(self) -> Money:
        total = ZERO
        for line in self.lines:
            total = total + line.subtotal()
        return total

    def vat(self) -> Money:
        total = ZERO
        for line in self.lines:
            total = total + line.subtotal().percent(VAT_RATE)
        return total

    def total(self) -> Money:
        return self.subtotal() + self.vat()

    def stock_lines(self) -> list[tuple[str, int]]:
        return [(line.product.sku, line.qty) for line in self.lines]

    def invoice(self) -> str:
        rows = [f"{line.product.name} × {line.qty}  {line.subtotal().format()}" for line in self.lines]
        rows.append(f"المجموع قبل الضريبة: {self.subtotal().format()}")
        rows.append(f"ضريبة القيمة المضافة 15%: {self.vat().format()}")
        rows.append(f"الإجمالي: {self.total().format()}")
        return "\n".join(rows)
