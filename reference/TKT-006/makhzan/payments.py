"""الدفع.

لم يصلنا توثيق مكتبة sadadpay وهي غير متاحة في بيئة التطوير، لذلك لم أكتب أي استدعاء لها.
هذا الملف يعرّف الواجهة التي سيلتزم بها المحوّل الحقيقي عندما يصل التوثيق.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from makhzan.money import Money


@dataclass(frozen=True)
class PaymentResult:
    ok: bool
    reference: str = ""
    reason: str = ""


class PaymentGateway(Protocol):
    def charge(self, amount: Money, order_ref: str) -> PaymentResult: ...


class PaymentFailed(Exception):
    pass


def pay(order, gateway: PaymentGateway, order_ref: str) -> PaymentResult:
    result = gateway.charge(order.total(), order_ref)
    if not result.ok:
        raise PaymentFailed(result.reason or "رفضت بوابة الدفع العملية")
    order.status = "paid"
    return result
