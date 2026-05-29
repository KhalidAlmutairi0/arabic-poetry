"""
Meilisearch index configurations.
This file defines how Arabic text is indexed and searched.
"""

VERSES_INDEX_CONFIG = {
    "primaryKey": "id",
    "searchableAttributes": [
        "full_verse_normalized",
        "hemistich_1_normalized",
        "hemistich_2_normalized",
        "poet_name_ar",
        "poem_title_ar",
    ],
    "filterableAttributes": [
        "poet_id",
        "poem_id",
        "poet_slug",
        "poem_slug",
        "is_famous",
        "era",
    ],
    "sortableAttributes": [
        "view_count",
        "share_count",
        "is_famous",
        "position",
    ],
    "rankingRules": [
        "words",
        "typo",
        "proximity",
        "attribute",
        "sort",
        "exactness",
    ],
    "typoTolerance": {
        "enabled": True,
        "minWordSizeForTypos": {
            "oneTypo": 4,
            "twoTypos": 8,
        },
    },
    "stopWords": [
        "ال", "في", "من", "إلى", "على", "عن", "مع", "إلا", "حتى",
        "و", "أو", "ثم", "لكن", "إن", "أن", "قد",
        "لا", "ما", "لم", "لن",
        "هو", "هي", "هم", "أنا", "نحن",
    ],
    "synonyms": {
        "حب": ["هوى", "عشق", "غرام", "وجد"],
        "حزن": ["كآبة", "غم", "أسى", "وجع"],
        "شوق": ["اشتياق", "حنين", "توق"],
        "فخر": ["اعتزاز", "كبرياء", "أنفة"],
        "موت": ["فناء", "ردى", "حتف", "هلاك"],
        "ليل": ["ظلام", "دجى"],
        "زمان": ["دهر", "أيام", "وقت"],
        "صحراء": ["قفر", "بيداء", "فلاة"],
    },
    "pagination": {"maxTotalHits": 2000},
}

POETS_INDEX_CONFIG = {
    "primaryKey": "id",
    "searchableAttributes": ["name_ar", "name_en", "era_label"],
    "filterableAttributes": ["era"],
    "sortableAttributes": ["poem_count", "verse_count"],
    "typoTolerance": {
        "enabled": True,
        "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 8},
    },
}

POEMS_INDEX_CONFIG = {
    "primaryKey": "id",
    "searchableAttributes": ["title_ar", "title_en", "poet_name_ar", "first_verse_normalized"],
    "filterableAttributes": ["poet_id", "era", "meter"],
    "sortableAttributes": ["view_count", "verse_count"],
}


ERA_LABELS = {
    "pre_islamic": "الجاهلية",
    "islamic_early": "صدر الإسلام",
    "umayyad": "الأموي",
    "abbasid": "العباسي",
    "andalusian": "الأندلسي",
    "mamluk": "المملوكي",
    "ottoman": "العثماني",
    "modern": "الحديث",
    "contemporary": "المعاصر",
}
