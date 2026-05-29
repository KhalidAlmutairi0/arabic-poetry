"""
Arabic text normalization for poetry search.
This is the most critical utility in the platform.
Order of operations matters — do not reorder steps.
"""

import re
import unicodedata


class ArabicNormalizer:
    # Diacritics: harakat, shadda, tanwin, maddah, sukun
    DIACRITICS = re.compile(
        r'[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۤۧۨ-ۭ]'
    )

    # Tatweel / kashida (ـ)
    TATWEEL = re.compile(r'ـ')

    # Hamza and Alef variants → bare Alef (ا)
    HAMZA_MAP = str.maketrans({
        'أ': 'ا',
        'إ': 'ا',
        'آ': 'ا',
        'ٱ': 'ا',
        'ؤ': 'و',
        'ئ': 'ي',
    })

    # Ta marbuta → Ha
    TA_MARBUTA = re.compile(r'ة')

    # Alef maqsura → Ya
    ALEF_MAQSURA = re.compile(r'ى')

    def normalize(
        self,
        text: str,
        remove_diacritics: bool = True,
        normalize_hamza: bool = True,
        normalize_ta_marbuta: bool = True,
        normalize_alef_maqsura: bool = False,
        remove_tatweel: bool = True,
    ) -> str:
        """
        Full normalization pipeline for search indexing and querying.
        Used before both indexing and querying — same transform = correct matching.
        """
        if not text:
            return ""

        # 1. Unicode normalization (NFC)
        text = unicodedata.normalize("NFC", text)

        # 2. Remove diacritics (harakat) — critical for search
        if remove_diacritics:
            text = self.DIACRITICS.sub("", text)

        # 3. Remove tatweel
        if remove_tatweel:
            text = self.TATWEEL.sub("", text)

        # 4. Normalize Hamza variants
        if normalize_hamza:
            text = text.translate(self.HAMZA_MAP)

        # 5. Normalize Ta Marbuta → Ha (end of word)
        if normalize_ta_marbuta:
            text = self.TA_MARBUTA.sub("ه", text)

        # 6. Normalize Alef Maqsura → Ya (optional, careful with poetry)
        if normalize_alef_maqsura:
            text = self.ALEF_MAQSURA.sub("ي", text)

        # 7. Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def normalize_for_display(self, text: str) -> str:
        """
        Light normalization — preserve diacritics for beautiful display.
        Only removes invisible/formatting characters.
        """
        if not text:
            return ""
        text = unicodedata.normalize("NFC", text)
        text = self.TATWEEL.sub("", text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def normalize_query(self, query: str) -> str:
        """
        Normalize a user search query.
        More aggressive: remove all noise to maximize recall.
        """
        return self.normalize(
            query,
            remove_diacritics=True,
            normalize_hamza=True,
            normalize_ta_marbuta=True,
            normalize_alef_maqsura=True,
            remove_tatweel=True,
        )

    def remove_definite_article(self, text: str) -> str:
        """Remove ال (definite article) from the beginning of words."""
        return re.sub(r'\bال', '', text)

    def extract_keywords(self, text: str, min_length: int = 3) -> list[str]:
        """Extract significant words from text for search/tagging."""
        normalized = self.normalize_query(text)
        words = normalized.split()
        # Filter short words and common stop words
        from app.utils.arabic_stop_words import ARABIC_STOP_WORDS
        return [w for w in words if len(w) >= min_length and w not in ARABIC_STOP_WORDS]

    def is_arabic(self, text: str) -> bool:
        """Check if text contains Arabic characters."""
        return bool(re.search(r'[؀-ۿ]', text))


# ── Slug generation for Arabic text ───────────────────

def arabic_to_slug(text: str, poet_name: str = "") -> str:
    """
    Convert Arabic text to URL-safe slug.
    Uses transliteration for Arabic characters.
    """
    from unidecode import unidecode
    import re

    # Transliterate Arabic to Latin
    slug = unidecode(text)

    # Lowercase and replace non-alphanumeric with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug.lower())
    slug = slug.strip('-')

    # Limit length
    if len(slug) > 100:
        slug = slug[:100].rstrip('-')

    return slug


# Singleton
normalizer = ArabicNormalizer()
