import unittest

from makhzan.money import ZERO, Money


class MoneyTests(unittest.TestCase):
    def test_from_riyals_rounds_half_up(self):
        self.assertEqual(Money.from_riyals("12.345").halalas, 1235)
        self.assertEqual(Money.from_riyals(3).halalas, 300)

    def test_rejects_float_halalas(self):
        with self.assertRaises(TypeError):
            Money(1.5)

    def test_arithmetic(self):
        self.assertEqual(Money(150) + Money(50), Money(200))
        self.assertEqual(Money(150) - Money(50), Money(100))
        self.assertEqual(Money(150) * 3, Money(450))

    def test_percent_rounds_half_up(self):
        self.assertEqual(Money(10).percent("0.15"), Money(2))  # 1.5 → 2
        self.assertEqual(Money(1000).percent("0.15"), Money(150))

    def test_format(self):
        self.assertEqual(Money(1250).format(), "12.50 ر.س")
        self.assertEqual(Money(-5).format(), "-0.05 ر.س")
        self.assertEqual(ZERO.format(), "0.00 ر.س")


if __name__ == "__main__":
    unittest.main()
