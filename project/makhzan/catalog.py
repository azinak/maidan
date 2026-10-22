"""كتالوج المنتجات والبحث فيه."""

from __future__ import annotations

from dataclasses import dataclass, field

from makhzan.money import Money


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price: Money
    tags: tuple[str, ...] = field(default_factory=tuple)


class Catalog:
    def __init__(self) -> None:
        self._products: dict[str, Product] = {}

    def add(self, product: Product) -> None:
        if not product.sku.strip():
            raise ValueError("رمز المنتج (SKU) مطلوب")
        if product.sku in self._products:
            raise ValueError(f"المنتج {product.sku} موجود مسبقًا")
        self._products[product.sku] = product

    def get(self, sku: str) -> Product:
        try:
            return self._products[sku]
        except KeyError:
            raise KeyError(f"لا يوجد منتج بالرمز {sku}") from None

    def __contains__(self, sku: object) -> bool:
        return sku in self._products

    def __len__(self) -> int:
        return len(self._products)

    def all(self) -> list[Product]:
        return sorted(self._products.values(), key=lambda p: p.sku)

    def search(self, query: str) -> list[Product]:
        """يعيد المنتجات التي يحتوي اسمها أو أحد وسومها على نص البحث."""
        q = query.strip().lower()
        if not q:
            return []
        return [
            p
            for p in self.all()
            if q in p.name.lower() or any(q in t.lower() for t in p.tags)
        ]
