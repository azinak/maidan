import unittest

from makhzan.catalog import Catalog
from tests.helpers import product


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.catalog.add(product("C1", "قهوة عربية", "35", "مشروبات"))
        self.catalog.add(product("T1", "شاي أخضر", "18", "مشروبات"))
        self.catalog.add(product("D1", "تمر سكري", "60", "تمور"))
        self.catalog.add(product("E1", "French Press", "95", "tools"))

    def test_duplicate_sku_rejected(self):
        with self.assertRaises(ValueError):
            self.catalog.add(product("C1", "أخرى", "1"))

    def test_get_missing(self):
        with self.assertRaises(KeyError):
            self.catalog.get("X")

    def test_search_by_name(self):
        self.assertEqual([p.sku for p in self.catalog.search("قهوة")], ["C1"])

    def test_search_by_tag(self):
        self.assertEqual([p.sku for p in self.catalog.search("مشروبات")], ["C1", "T1"])

    def test_search_case_insensitive_latin(self):
        self.assertEqual([p.sku for p in self.catalog.search("french")], ["E1"])

    def test_empty_query(self):
        self.assertEqual(self.catalog.search("   "), [])


if __name__ == "__main__":
    unittest.main()
