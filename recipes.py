"""
recipes.py - AI-Powered and Offline Recipe Suggestions for GrocoPilot.
---------------------------------------------------------------------
Suggests simple, home-style Indian recipes prioritizing items that are
closest to spoiling, helping prevent food waste.

Rules & Guarantees:
  1. Only unexpired, active items are considered.
  2. Prioritizes items in RED (<=2 days left) and YELLOW (3-5 days left).
  3. Recommends 3 practical home-style Indian dishes.
  4. Extra ingredients are strictly limited to common pantry staples.
  5. Never makes health or safety claims.
  6. Robust fallback to local recipes (data/recipes.json) if offline or API key is absent.
"""

from __future__ import annotations
from datetime import date
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import db
import logic
import scanner

RECIPES_JSON = Path(__file__).parent / "data" / "recipes.json"


def get_cookable_items(max_days_ahead: int = 14, db_path: Path = db.DB_FILE) -> List[Dict[str, Any]]:
    """
    Retrieves all active items from the database that are NOT expired.
    Sorts by days left ascending so items needing attention come first.
    Filters out items where days_left < 0.
    """
    active_items = db.get_active_items(db_path=db_path)
    today = date.today()
    cookable: List[Dict[str, Any]] = []

    for item in active_items:
        band = logic.get_urgency_band(item["expiry_date"], as_of_date=today)
        days_left = band["days_left"]

        # Only unexpired items within reasonable cooking horizon
        if days_left >= 0 and days_left <= max_days_ahead:
            cookable.append({
                **item,
                "days_left": days_left,
                "urgency_label": band["label"],
                "badge": band["badge"],
            })

    # Sort so smallest days_left comes first
    cookable.sort(key=lambda x: x["days_left"])
    return cookable


def load_offline_recipes() -> List[Dict[str, Any]]:
    """Loads backup recipes from data/recipes.json for offline / fallback use."""
    if not RECIPES_JSON.exists():
        return []
    try:
        with open(RECIPES_JSON, mode="r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def get_offline_suggestions(cookable_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Matches cookable items from the fridge against the offline recipes database.
    Scores each recipe by how many expiring items it utilizes.
    Returns the top 3 best matching recipes.
    """
    offline_db = load_offline_recipes()
    if not offline_db or not cookable_items:
        return offline_db[:3] if offline_db else []

    fridge_names = [it["name"].lower() for it in cookable_items]

    scored_recipes: List[Tuple[int, Dict[str, Any]]] = []
    for recipe in offline_db:
        score = 0
        uses = recipe.get("uses_items", [])
        for req in uses:
            for item in cookable_items:
                name_clean = item["name"].lower()
                if req in name_clean or name_clean in req:
                    # Give higher weight if item is urgent (RED <= 2 days)
                    weight = 3 if item["days_left"] <= 2 else 1
                    score += weight
                    break
        scored_recipes.append((score, recipe))

    # Sort descending by score
    scored_recipes.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored_recipes[:3]]


def suggest_recipes(cookable_items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Generates 3 home-style Indian recipe recommendations using items closest to spoiling.
    Tries Gemini Flash Vision/Text model first.
    If offline or API fails, smoothly falls back to local data/recipes.json.
    
    Returns:
      {
        "status": "ok" | "fallback" | "no_items",
        "recipes": List[Dict[str, Any]],
        "source": "ai" | "offline",
        "error": Optional[str]
      }
    """
    if cookable_items is None:
        cookable_items = get_cookable_items()

    if not cookable_items:
        return {
            "status": "no_items",
            "recipes": [],
            "source": "none",
            "message": "No unexpired items currently in your kitchen! Add groceries to see recipe suggestions.",
        }

    # Format ingredients for prompt
    items_desc_list = [
        f"- {it['name']} ({it['quantity']} {it['unit']}, {it['days_left']} days left until expiry, {it['storage']})"
        for it in cookable_items
    ]
    items_text = "\n".join(items_desc_list)

    prompt = f"""
    You are an expert home-style Indian chef helping a family prevent food waste.
    Here is the list of groceries currently in their kitchen, sorted by days left until expiry:

    {items_text}

    RULES FOR RECIPE SUGGESTIONS:
    1. Suggest EXACTLY 3 simple, practical, home-style Indian recipes (e.g. sabzi, bhurji, dal, khichdi, toast, paratha).
    2. Prioritize items with the fewest days left (highest urgency).
    3. Use mainly the ingredients listed above.
    4. Anything not listed above MUST be put in "needs_extra" and MUST be limited to everyday Indian pantry staples (such as cooking oil, salt, cumin seeds, mustard seeds, turmeric, chilli powder, wheat flour).
    5. Keep steps short and clear (3 to 5 concise instructions).
    6. Do NOT make any medical, health, or food-safety claims.
    7. NEVER suggest using any expired items.
    8. In "why_now", briefly explain which urgent ingredients this recipe rescues from spoiling.

    Output strictly valid JSON with this schema:
    {{
      "recipes": [
        {{
          "title": "Recipe Title",
          "uses_items": ["item1", "item2"],
          "needs_extra": ["oil", "salt"],
          "time_minutes": 15,
          "steps": [
            "Step 1 instructions",
            "Step 2 instructions",
            "Step 3 instructions"
          ],
          "why_now": "Uses up fresh spinach and paneer before they spoil."
        }}
      ]
    }}
    """

    client = scanner.get_gemini_client()
    if client:
        try:
            from google.genai import types

            scanner.increment_api_call_count()
            response = client.models.generate_content(
                model=scanner.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )

            if response and response.text:
                data = json.loads(response.text.strip())
                recipes = data.get("recipes", [])
                if recipes and isinstance(recipes, list):
                    return {
                        "status": "ok",
                        "recipes": recipes,
                        "source": "ai",
                        "error": None,
                    }
        except Exception:
            pass  # Fall through to offline fallback

    # Fallback to local recipe matching
    fallback_recipes = get_offline_suggestions(cookable_items)
    return {
        "status": "fallback",
        "recipes": fallback_recipes,
        "source": "offline",
        "error": "AI service offline or API key not set. Showing curated offline home recipes matching your items.",
    }
