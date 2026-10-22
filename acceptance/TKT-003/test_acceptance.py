import unittest
from datetime import date

from makhzan.catalog import Product
from makhzan.money import Money
from makhzan.orders import Order


def order_of(riyals):
    o = Order()
    o.add(Product(sku="A", name="منتج", price=Money.from_riyals(riyals)), 1)
    return o


TODAY = date(2026, 3, 1)


class Discounts(unittest.TestCase):
    def setUp(self):
        from makhzan.discounts import Discount, DiscountError
        self.D = Discount
        self.E = DiscountError

    def test_percent(self):
        o = order_of("200")
        o.apply_discount(self.D("RAMADAN10", "percent", "10"), TODAY)
        self.assertEqual(o.discount_amount(), Money(2000))
        self.assertEqual(o.vat(), Money(2700))  # 180 × 15%
        self.assertEqual(o.total(), Money(20700))

    def test_percent_rounds_half_up(self):
        o = order_of("0.25")
        o.apply_discount(self.D("X", "percent", "10"), TODAY)  # 2.5 هللة → 3
        self.assertEqual(o.discount_amount(), Money(3))

    def test_fixed(self):
        o = order_of("100")
        o.apply_discount(self.D("WELCOME", "fixed", "20"), TODAY)
        self.assertEqual(o.discount_amount(), Money(2000))
        self.assertEqual(o.total(), Money(9200))

    def test_fixed_capped_at_subtotal(self):
        o = order_of("10")
        o.apply_discount(self.D("BIG", "fixed", "50"), TODAY)
        self.assertEqual(o.discount_amount(), Money(1000))
        self.assertEqual(o.total(), Money(0))

    def test_expired(self):
        o = order_of("100")
        with self.assertRaises(self.E):
            o.apply_discount(self.D("OLD", "fixed", "5", expires=date(2026, 2, 28)), TODAY)
        self.assertEqual(o.discount_amount(), Money(0))

    def test_expiry_day_inclusive(self):
        o = order_of("100")
        o.apply_discount(self.D("LAST", "fixed", "5", expires=TODAY), TODAY)
        self.assertEqual(o.discount_amount(), Money(500))

    def test_min_subtotal(self):
        o = order_of("99")
        with self.assertRaises(self.E):
            o.apply_discount(self.D("MIN", "fixed", "5", min_subtotal=Money(10000)), TODAY)
        o2 = order_of("100")
        o2.apply_discount(self.D("MIN", "fixed", "5", min_subtotal=Money(10000)), TODAY)
        self.assertEqual(o2.discount_amount(), Money(500))

    def test_no_stacking(self):
        o = order_of("100")
        o.apply_discount(self.D("A", "fixed", "5"), TODAY)
        with self.assertRaises(self.E):
            o.apply_discount(self.D("B", "fixed", "5"), TODAY)
        self.assertEqual(o.discount_amount(), Money(500))

    def test_unknown_kind(self):
        with self.assertRaises(ValueError):
            order_of("100").apply_discount(self.D("Z", "bogo", "1"), TODAY)

    def test_no_discount(self):
        o = order_of("100")
        self.assertEqual(o.discount_amount(), Money(0))
        self.assertEqual(o.total(), Money(11500))

    def test_invoice_shows_discount(self):
        o = order_of("100")
        o.apply_discount(self.D("WELCOME", "fixed", "20"), TODAY)
        text = o.invoice()
        self.assertIn("20.00 ر.س", text)
        self.assertIn("92.00 ر.س", text)
