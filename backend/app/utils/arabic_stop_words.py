"""
Arabic stop words for search filtering.
These are high-frequency words that carry little search value.
Note: Some poetic particles (like يا) are intentionally kept.
"""

ARABIC_STOP_WORDS = frozenset([
    # Definite article
    "ال",

    # Prepositions
    "في", "من", "إلى", "على", "عن", "مع", "إلا", "حتى", "منذ",
    "خلال", "بين", "تحت", "فوق", "أمام", "خلف", "عند", "لدى",

    # Conjunctions
    "و", "أو", "ثم", "لكن", "بل", "أما", "فـ", "وـ",

    # Pronouns
    "هو", "هي", "هم", "هن", "أنا", "نحن", "أنت", "أنتم", "أنتن",
    "هذا", "هذه", "ذلك", "تلك", "هؤلاء", "أولئك",

    # Relative pronouns
    "الذي", "التي", "الذين", "اللاتي", "اللواتي",

    # Demonstratives
    "هنا", "هناك", "هنالك",

    # High-frequency verbs
    "كان", "كانت", "كانوا", "يكون", "تكون",
    "قال", "قالت", "قالوا", "يقول",
    "ذهب", "جاء", "جاءت",

    # Particles
    "لا", "ما", "لم", "لن", "قد", "إن", "أن", "لأن",
    "إذا", "لو", "لولا", "حيث", "كيف", "متى",

    # Question words (keep for search)
    # "من" already above, "ما" already above
    # "كيف", "متى", "أين" — keep if useful

    # Common preposition+pronoun combos
    "له", "لها", "لهم", "بها", "بهم", "عليه", "عليها",
    "فيه", "فيها", "فيهم", "منه", "منها", "منهم",
    "إليه", "إليها", "إليهم",
])
