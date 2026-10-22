"""أكواد الخصم."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from makhzan.money import ZERO, Money


class DiscountError(Exception):
    """لا يمكن تطبيق كود الخصم على هذا الطلب."""


@dataclass(frozen=True)
class Discount:
    code: str
    kind: str
    value: str
    min_subtotal: Money = ZERO
    expires: date | None = None
