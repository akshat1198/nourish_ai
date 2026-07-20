"""Public config the UI reads — currently the nutrition-goal cutoffs, so the
questionnaire can show what 'low-fat' etc. actually mean without hardcoding
numbers that could drift from `settings`."""
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/v1", tags=["config"])


@router.get("/config")
def get_config():
    s = settings
    return {
        "nutrition_goals": [
            {"value": "high_protein", "hint": f"≥{s.NUTRI_HIGH_PROTEIN_G:g} g protein"},
            {"value": "low_calorie", "hint": f"≤{s.NUTRI_LOW_CALORIE_KCAL:g} kcal"},
            {"value": "low_fat", "hint": f"≤{s.NUTRI_LOW_FAT_G:g} g fat"},
            {"value": "low_carb", "hint": f"≤{s.NUTRI_LOW_CARB_G:g} g carbs"},
        ]
    }
