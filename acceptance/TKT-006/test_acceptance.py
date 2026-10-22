import importlib
import pkgutil
import sys
import unittest


class _BlockSadadPay:
    """المكتبة sadadpay غير موجودة في بيئة التشغيل الحقيقية."""

    def find_spec(self, name, path=None, target=None):
        if name == "sadadpay" or name.startswith("sadadpay."):
            raise ImportError("sadadpay is not installed")
        return None


class StillShippable(unittest.TestCase):
    def setUp(self):
        sys.meta_path.insert(0, _BlockSadadPay())
        for mod in [m for m in sys.modules if m == "makhzan" or m.startswith("makhzan.")]:
            del sys.modules[mod]

    def tearDown(self):
        sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, _BlockSadadPay)]

    def test_every_module_imports_without_sadadpay(self):
        import makhzan
        for info in pkgutil.iter_modules(makhzan.__path__):
            importlib.import_module(f"makhzan.{info.name}")

    def test_orders_still_work(self):
        from makhzan.catalog import Product
        from makhzan.money import Money
        from makhzan.orders import Order
        o = Order()
        o.add(Product(sku="A", name="منتج", price=Money(10000)), 1)
        self.assertEqual(o.total(), Money(11500))
        self.assertEqual(o.status, "draft")
