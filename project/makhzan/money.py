"""المبالغ المالية.

قاعدة الفريق: كل مبلغ يُخزَّن عددًا صحيحًا بالهللة (1 ريال = 100 هللة).
لا نستخدم float للمال أبدًا، والتقريب دائمًا نصف للأعلى (ROUND_HALF_UP).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


@dataclass(frozen=True, order=True)
class Money:
    halalas: int

    def __post_init__(self) -> None:
        if isinstance(self.halalas, bool) or not isinstance(self.halalas, int):
            raise TypeError("المبلغ يجب أن يكون عددًا صحيحًا بالهللة")

    @classmethod
    def from_riyals(cls, value: str | int | Decimal) -> Money:
        try:
            amount = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"مبلغ غير صالح: {value!r}") from exc
        halalas = (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return cls(int(halalas))

    def __add__(self, other: Money) -> Money:
        return Money(self.halalas + other.halalas)

    def __sub__(self, other: Money) -> Money:
        return Money(self.halalas - other.halalas)

    def __mul__(self, qty: int) -> Money:
        if not isinstance(qty, int):
            raise TypeError("الكمية يجب أن تكون عددًا صحيحًا")
        return Money(self.halalas * qty)

    def percent(self, rate: str | Decimal) -> Money:
        """نسبة من المبلغ مقرّبة لأقرب هللة (نصف للأعلى). rate=0.15 تعني 15%."""
        value = (Decimal(self.halalas) * Decimal(str(rate))).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return Money(int(value))

    def format(self) -> str:
        sign = "-" if self.halalas < 0 else ""
        riyals, halalas = divmod(abs(self.halalas), 100)
        return f"{sign}{riyals}.{halalas:02d} ر.س"


ZERO = Money(0)
