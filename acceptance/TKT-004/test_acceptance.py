import unittest

from makhzan.inventory import Inventory, OutOfStock


class DuplicateLines(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory()
        self.inv.receive("D1", 5)
        self.inv.receive("E1", 4)

    def test_reported_case(self):
        with self.assertRaises(OutOfStock) as ctx:
            self.inv.reserve([("D1", 3), ("D1", 3)])
        self.assertEqual(self.inv.available("D1"), 5)
        self.assertEqual(ctx.exception.requested, 6)
        self.assertEqual(ctx.exception.available, 5)

    def test_duplicates_within_stock(self):
        self.inv.reserve([("D1", 2), ("E1", 1), ("D1", 3)])
        self.assertEqual(self.inv.available("D1"), 0)
        self.assertEqual(self.inv.available("E1"), 3)

    def test_atomic_with_duplicates(self):
        with self.assertRaises(OutOfStock):
            self.inv.reserve([("E1", 2), ("D1", 4), ("D1", 2)])
        self.assertEqual(self.inv.available("D1"), 5)
        self.assertEqual(self.inv.available("E1"), 4)

    def test_never_negative(self):
        for lines in ([("D1", 6)], [("D1", 1)] * 6, [("X", 1)]):
            with self.assertRaises(OutOfStock):
                self.inv.reserve(lines)
        self.assertEqual(self.inv.available("D1"), 5)

    def test_non_positive_quantities(self):
        for bad in (0, -2):
            with self.assertRaises(ValueError):
                self.inv.reserve([("D1", bad)])
            with self.assertRaises(ValueError):
                self.inv.release([("D1", bad)])
        self.assertEqual(self.inv.available("D1"), 5)
