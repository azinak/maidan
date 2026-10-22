import unittest

from makhzan.catalog import Product
from makhzan.money import Money
from makhzan.orders import Order


def p(sku, riyals):
    return Product(sku=sku, name=sku, price=Money.from_riyals(riyals))


class VatOnOrderTotal(unittest.TestCase):
    def test_reported_invoice(self):
        order = Order()
        for sku in ("A", "B", "C"):
            order.add(p(sku, "0.10"))
        self.assertEqual(order.vat(), Money(5))
        self.assertEqual(order.total(), Money(35))

    def test_many_small_lines(self):
        order = Order()
        for i in range(7):
            order.add(p(f"S{i}", "0.03"))
        # 21 هللة × 15% = 3.15 → 3
        self.assertEqual(order.vat(), Money(3))
        self.assertEqual(order.total(), Money(24))

    def test_round_half_up_on_total(self):
        order = Order()
        order.add(p("A", "0.10"), 1)
        order.add(p("B", "0.20"), 1)
        # 30 هللة × 15% = 4.5 → 5
        self.assertEqual(order.vat(), Money(5))

    def test_normal_order_unchanged(self):
        order = Order()
        order.add(p("A", "100"), 2)
        order.add(p("B", "33.33"), 1)
        # 23333 × 0.15 = 3499.95 → 3500
        self.assertEqual(order.vat(), Money(3500))
        self.assertEqual(order.total(), Money(26833))

    def test_invoice_shows_correct_vat(self):
        order = Order()
        for sku in ("A", "B", "C"):
            order.add(p(sku, "0.10"))
        text = order.invoice()
        self.assertIn("0.05 ر.س", text)
        self.assertIn("0.35 ر.س", text)

    def test_empty_order(self):
        self.assertEqual(Order().vat(), Money(0))
        self.assertEqual(Order().total(), Money(0))
