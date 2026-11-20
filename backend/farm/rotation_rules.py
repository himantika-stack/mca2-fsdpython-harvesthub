"""Editable, conservative crop-family rotation prompts.

These are planning prompts only, not agronomic advice. A farmer should validate a choice with
local soil, pest, weather, market, and agronomy information before planting.
"""

FAMILY_KEYWORDS = {
    "legume": ("bean", "pea", "lentil", "chickpea", "gram", "soy", "groundnut"),
    "cereal": ("rice", "wheat", "maize", "corn", "millet", "sorghum", "barley"),
    "solanaceous": ("tomato", "potato", "brinjal", "eggplant", "pepper", "chilli"),
    "brassica": ("cabbage", "cauliflower", "broccoli", "mustard", "radish"),
    "cucurbit": ("cucumber", "pumpkin", "melon", "gourd", "squash"),
}

NEXT_FAMILIES = {
    "legume": ("cereal", "brassica", "cucurbit"),
    "cereal": ("legume", "brassica", "cucurbit"),
    "solanaceous": ("legume", "cereal", "brassica"),
    "brassica": ("legume", "cereal", "cucurbit"),
    "cucurbit": ("legume", "cereal", "brassica"),
}


def family_for(crop_name):
    lower_name = crop_name.lower()
    return next((family for family, keywords in FAMILY_KEYWORDS.items() if any(word in lower_name for word in keywords)), None)


def recommendation_for(crop_name):
    family = family_for(crop_name)
    if not family:
        return {"previous_family": None, "recommended_families": [], "message": "No configured crop-family rule matches this crop. Review local rotation guidance before choosing the next crop."}
    suggested = NEXT_FAMILIES[family]
    return {"previous_family": family, "recommended_families": suggested, "message": "Rule-based planning prompt only: choose a different listed family where it fits local conditions; this is not agronomic validation."}
