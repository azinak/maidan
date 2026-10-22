"""استيراد المنتجات من ملف CSV يرسله المورّد."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from makhzan.catalog import Catalog, Product
from makhzan.money import Money

REQUIRED = ("sku", "name", "price")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


@dataclass
class ImportReport:
    added: list[str] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)


def _parse_price(raw: str) -> Money:
    try:
        value = Decimal(raw.translate(_ARABIC_DIGITS))
    except InvalidOperation:
        raise ValueError(f"سعر غير صالح: {raw!r}") from None
    if not value.is_finite() or value < 0:
        raise ValueError(f"سعر غير صالح: {raw!r}")
    return Money.from_riyals(value)


def import_products(csv_text: str, catalog: Catalog) -> ImportReport:
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        raise ValueError("الملف فارغ")
    header = [h.strip().lower() for h in rows[0]]
    missing = [col for col in REQUIRED if col not in header]
    if missing:
        raise ValueError(f"أعمدة مطلوبة غير موجودة: {', '.join(missing)}")
    col = {name: header.index(name) for name in header}

    report = ImportReport()
    for line_no, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue

        def cell(name: str) -> str:
            i = col.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        sku, name = cell("sku"), cell("name")
        if not sku:
            report.errors.append((line_no, "رمز المنتج فارغ"))
            continue
        if not name:
            report.errors.append((line_no, "اسم المنتج فارغ"))
            continue
        if sku in catalog:
            report.errors.append((line_no, f"الرمز {sku} مكرر"))
            continue
        try:
            price = _parse_price(cell("price"))
        except ValueError as exc:
            report.errors.append((line_no, str(exc)))
            continue
        tags = tuple(t.strip() for t in cell("tags").split("|") if t.strip())
        catalog.add(Product(sku=sku, name=name, price=price, tags=tags))
        report.added.append(sku)
    return report
