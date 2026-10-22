import unittest

from makhzan.inventory import Inventory, OutOfStock


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory()
        self.inv.receive("A", 5)
        self.inv.receive("B", 2)

    def test_receive_positive_only(self):
        with self.assertRaises(ValueError):
            self.inv.receive("A", 0)

    def test_reserve_deducts(self):
        self.inv.reserve([("A", 2), ("B", 1)])
        self.assertEqual(self.inv.available("A"), 3)
        self.assertEqual(self.inv.available("B"), 1)

    def test_reserve_is_all_or_nothing(self):
        with self.assertRaises(OutOfStock):
            self.inv.reserve([("A", 2), ("B", 3)])
        self.assertEqual(self.inv.available("A"), 5)
        self.assertEqual(self.inv.available("B"), 2)

    def test_release(self):
        self.inv.reserve([("A", 2)])
        self.inv.release([("A", 2)])
        self.assertEqual(self.inv.available("A"), 5)


if __name__ == "__main__":
    unittest.main()
