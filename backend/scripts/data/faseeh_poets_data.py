"""
Faseeh (classical Arabic) poets data.

Classical poets are now imported automatically via scripts/deep_fetch.py
from the live api.qafiyah.com corpus. This file is kept as an empty list
so seed_large.py continues to work correctly.

To add hand-curated poets, append dicts with this shape:
{
    "name_ar":      str,          # Arabic name
    "slug":         str,          # URL-safe slug (must be unique)
    "bio_ar":       str,          # Arabic biography
    "era":          str,          # One of: pre_islamic, islamic, umayyad,
                                  #   abbasid, andalusian, modern, contemporary
    "nationality_ar": str,        # e.g. "عربي", "مصري"
    "is_verified":  bool,
    "metadata_":    dict,
    "poems": [
        {
            "title_ar":    str,
            "meter":       str | None,
            "era":         str,
            "is_verified": bool,
            "categories":  list[str],   # slugs from categories_data
            "verses": [
                {"h1": str, "h2": str},  # h2 optional
                ...
            ],
        },
        ...
    ],
}
"""

FASEEH_POETS: list[dict] = []
