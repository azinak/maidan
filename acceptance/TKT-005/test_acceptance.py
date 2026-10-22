import unittest

from makhzan.catalog import Catalog, Product
from makhzan.money import Money


class CsvImport(unittest.TestCase):
    def setUp(self):
        from makhzan.importer import import_products
        self.imp = import_products
        self.cat = Catalog()
        self.cat.add(Product(sku="OLD", name="قديم", price=Money(100)))

    def test_happy_path(self):
        text = "sku,name,price,tags\nC1,قهوة عربية,35,مشروبات|بن\nT1,شاي,18.5,\n"
        r = self.imp(text, self.cat)
        self.assertEqual(r.added, ["C1", "T1"])
        self.assertEqual(r.errors, [])
        self.assertEqual(self.cat.get("C1").price, Money(3500))
        self.assertEqual(self.cat.get("C1").tags, ("مشروبات", "بن"))
        self.assertEqual(self.cat.get("T1").price, Money(1850))
        self.assertEqual(self.cat.get("T1").tags, ())

    def test_column_order_and_whitespace(self):
        text = "price , sku,name\n 12.5 ,  A1 ,  تمر  \n"
        r = self.imp(text, self.cat)
        self.assertEqual(r.added, ["A1"])
        self.assertEqual(self.cat.get("A1").name, "تمر")
        self.assertEqual(self.cat.get("A1").price, Money(1250))

    def test_arabic_digits(self):
        text = "sku,name,price\nA1,تمر,١٢٫٥٠\nA2,بن,٣\n"
        r = self.imp(text, self.cat)
        self.assertEqual(r.added, ["A1", "A2"])
        self.assertEqual(self.cat.get("A1").price, Money(1250))
        self.assertEqual(self.cat.get("A2").price, Money(300))

    def test_bad_rows_reported_with_line_numbers(self):
        text = "\n".join([
            "sku,name,price",
            "A1,جيد,10",       # 2 ok
            ",بلا رمز,10",      # 3 empty sku
            "A2,,10",          # 4 empty name
            "A1,مكرر,10",      # 5 duplicate in file
            "OLD,موجود,10",    # 6 duplicate in catalog
            "A3,سعر,abc",      # 7 bad price
            "A4,سالب,-1",      # 8 negative
            "",                # 9 blank ignored
            "A5,جيد,0.5",      # 10 ok
        ])
        r = self.imp(text, self.cat)
        self.assertEqual(r.added, ["A1", "A5"])
        self.assertEqual([n for n, _ in r.errors], [3, 4, 5, 6, 7, 8])
        for _, reason in r.errors:
            self.assertTrue(reason.strip())

    def test_missing_required_column(self):
        with self.assertRaises(ValueError):
            self.imp("sku,price\nA1,10\n", self.cat)
        self.assertNotIn("A1", self.cat)
