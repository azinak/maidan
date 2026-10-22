"""تطبيع النص العربي لأغراض البحث."""

from __future__ import annotations

import re

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي"})


def normalize_arabic(text: str) -> str:
    """يحذف التشكيل والتطويل ويوحّد أشكال الألف والتاء المربوطة والألف المقصورة."""
    return _TASHKEEL.sub("", text).translate(_MAP).lower().strip()
