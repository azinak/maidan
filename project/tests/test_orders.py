import unittest

from makhzan.money import Money
from makhzan.orders import Order
from tests.helpers import product


class OrderTests(unittest.TestCase):
    def test_add_merges_same_product(self):
        order = Order()
        coffee = product("C1", "قهوة", "35")
        order.add(coffee, 1)
        order.add(coffee, 2)
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.lines[0].qty, 3)

    def test_add_rejects_non_positive(self):
        with self.assertRaises(ValueError):
            Order().add(product("C1", "قهوة", "35"), 0)

    def test_totals(self):
        order = Order()
        order.add(product("C1", "قهوة", "100"), 2)
        self.assertEqual(order.subtotal(), Money(20000))
        self.assertEqual(order.vat(), Money(3000))
        self.assertEqual(order.total(), Money(23000))

    def test_invoice_mentions_total(self):
        order = Order()
        order.add(product("C1", "قهوة", "100"), 1)
        self.assertIn("115.00 ر.س", order.invoice())


if __name__ == "__main__":
    unittest.main()
