import unittest

from makhzan.catalog import Catalog, Product
from makhzan.money import Money


def p(sku, name, *tags):
    return Product(sku=sku, name=name, price=Money(100), tags=tuple(tags))


class NormalizeArabic(unittest.TestCase):
    def setUp(self):
        from makhzan.text import normalize_arabic
        self.n = normalize_arabic

    def test_alef_forms(self):
        self.assertEqual(self.n("أحمد إبراهيم آمنة ٱلله"), self.n("احمد ابراهيم امنه الله"))

    def test_taa_marbuta_and_alef_maqsura(self):
        self.assertEqual(self.n("قهوة"), self.n("قهوه"))
        self.assertEqual(self.n("مستشفى"), self.n("مستشفي"))

    def test_tashkeel_and_tatweel_removed(self):
        self.assertEqual(self.n("قَهْوَةٌ"), self.n("قهوة"))
        self.assertEqual(self.n("قهــــوة"), self.n("قهوة"))
        self.assertEqual(self.n("مُحَمَّدٌ"), self.n("محمد"))

    def test_latin_lower_and_strip(self):
        self.assertEqual(self.n("  French PRESS "), "french press")


class SearchUsesNormalization(unittest.TestCase):
    def setUp(self):
        self.c = Catalog()
        self.c.add(p("P1", "عطر أحمد", "عطور"))
        self.c.add(p("P2", "قهوة عربية", "مشروبات"))
        self.c.add(p("P3", "حلوى المستشفى"))
        self.c.add(p("P4", "إبريق شاي", "أدوات"))
        self.c.add(p("P5", "French Press", "Tools"))

    def ids(self, q):
        return [x.sku for x in self.c.search(q)]

    def test_hamza(self):
        self.assertEqual(self.ids("احمد"), ["P1"])
        self.assertEqual(self.ids("ابريق"), ["P4"])

    def test_taa_marbuta(self):
        self.assertEqual(self.ids("قهوه"), ["P2"])

    def test_query_with_tashkeel(self):
        self.assertEqual(self.ids("قَهْوَة"), ["P2"])

    def test_alef_maqsura(self):
        self.assertEqual(self.ids("حلوي"), ["P3"])

    def test_tags_normalized(self):
        self.assertEqual(self.ids("ادوات"), ["P4"])

    def test_existing_behaviour(self):
        self.assertEqual(self.ids("tools"), ["P5"])
        self.assertEqual(self.ids("  "), [])
        self.assertEqual(self.ids("ا"), ["P1", "P2", "P3", "P4"])
