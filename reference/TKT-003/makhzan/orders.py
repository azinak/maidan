"""الطلبات والفواتير."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from datetime import date

from makhzan.catalog import Product
from makhzan.discounts import Discount, DiscountError
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
    discount: Discount | None = None

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

    def apply_discount(self, discount: Discount, today: date) -> None:
        if discount.kind not in ("percent", "fixed"):
            raise ValueError(f"نوع خصم غير معروف: {discount.kind}")
        if self.discount is not None:
            raise DiscountError("على الطلب خصم مطبّق مسبقًا، ولا يمكن جمع خصمين")
        if discount.expires is not None and today > discount.expires:
            raise DiscountError(f"انتهت صلاحية الكود {discount.code}")
        if self.subtotal() < discount.min_subtotal:
            raise DiscountError(
                f"الكود {discount.code} يتطلب طلبًا بقيمة {discount.min_subtotal.format()} على الأقل"
            )
        self.discount = discount

    def discount_amount(self) -> Money:
        if self.discount is None:
            return ZERO
        subtotal = self.subtotal()
        if self.discount.kind == "percent":
            amount = subtotal.percent(Decimal(self.discount.value) / 100)
        else:
            amount = Money.from_riyals(self.discount.value)
        return min(amount, subtotal)

    def vat(self) -> Money:
        # الضريبة تُحسب مرة واحدة على المجموع بعد الخصم وتُقرَّب مرة واحدة.
        return (self.subtotal() - self.discount_amount()).percent(VAT_RATE)

    def total(self) -> Money:
        return self.subtotal() - self.discount_amount() + self.vat()

    def stock_lines(self) -> list[tuple[str, int]]:
        return [(line.product.sku, line.qty) for line in self.lines]

    def invoice(self) -> str:
        rows = [f"{line.product.name} × {line.qty}  {line.subtotal().format()}" for line in self.lines]
        rows.append(f"المجموع قبل الضريبة: {self.subtotal().format()}")
        if self.discount is not None:
            rows.append(f"خصم ({self.discount.code}): {self.discount_amount().format()}")
        rows.append(f"ضريبة القيمة المضافة 15%: {self.vat().format()}")
        rows.append(f"الإجمالي: {self.total().format()}")
        return "\n".join(rows)
