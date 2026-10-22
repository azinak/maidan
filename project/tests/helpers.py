from makhzan.catalog import Product
from makhzan.money import Money


def product(sku: str, name: str, riyals: str, *tags: str) -> Product:
    return Product(sku=sku, name=name, price=Money.from_riyals(riyals), tags=tuple(tags))
