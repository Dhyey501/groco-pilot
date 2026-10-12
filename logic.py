"""
logic.py - Core expiry, urgency bands, and shelf-life logic for GrocoPilot.
---------------------------------------------------------------------------
This module contains the business rules of the app:
  1. Shelf-life lookup from data/shelf_life.csv
  2. Matching food names to shelf life records (exact or fuzzy)
  3. Priority of date sources: typed > scanned > estimated
  4. Estimated expiry calculation = purchase_date + shelf_days
  5. "Opened-pack clock" = min(current_expiry, opened_date + opened_fridge_days)
  6. Urgency bands (RED: expired or <=2 days, YELLOW: 3-5 days, GREEN: >5 days)
  7. Strict date validation (reject years before 2020 or > 5 years in future)
"""

from __future__ import annotations
import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import db

# Path to the shelf life CSV file
SHELF_LIFE_CSV = Path(__file__).parent / "data" / "shelf_life.csv"

# Global in-memory cache for shelf life data so we don't re-read disk constantly
_SHELF_LIFE_CACHE: Optional[List[Dict[str, Any]]] = None


def load_shelf_life_table(csv_path: Path = SHELF_LIFE_CSV) -> List[Dict[str, Any]]:
    """
    Loads and caches the shelf-life rules from shelf_life.csv.
    Ignores comment lines starting with '#'.
    Returns a list of dicts with keys:
      food, category, keywords, fridge_days, room_days, freezer_days, opened_fridge_days
    """
    global _SHELF_LIFE_CACHE
    if _SHELF_LIFE_CACHE is not None:
        return _SHELF_LIFE_CACHE

    records: List[Dict[str, Any]] = []
    if not csv_path.exists():
        _SHELF_LIFE_CACHE = records
        return records

    with open(csv_path, mode="r", encoding="utf-8") as f:
        # Filter out lines that start with '#'
        lines = [line for line in f if not line.strip().startswith("#")]

    reader = csv.DictReader(lines)
    for row in reader:
        records.append({
            "food": row.get("food", "").strip().lower(),
            "category": row.get("category", "General").strip(),
            "keywords": [
                kw.strip().lower()
                for kw in row.get("keywords", "").split("|")
                if kw.strip()
            ],
            "fridge_days": int(row["fridge_days"]) if row.get("fridge_days", "").strip() else None,
            "room_days": int(row["room_days"]) if row.get("room_days", "").strip() else None,
            "freezer_days": int(row["freezer_days"]) if row.get("freezer_days", "").strip() else None,
            "opened_fridge_days": int(row["opened_fridge_days"]) if row.get("opened_fridge_days", "").strip() else None,
        })

    _SHELF_LIFE_CACHE = records
    return _SHELF_LIFE_CACHE


def reload_shelf_life_cache() -> None:
    """Clears cache to force reload if shelf_life.csv is modified."""
    global _SHELF_LIFE_CACHE
    _SHELF_LIFE_CACHE = None


def get_all_food_names() -> List[str]:
    """Returns a list of all canonical food names in the shelf-life table for UI autocomplete."""
    table = load_shelf_life_table()
    return sorted([item["food"] for item in table])


def get_all_categories() -> List[str]:
    """Returns a unique sorted list of all categories in the shelf-life table."""
    table = load_shelf_life_table()
    categories = {item["category"] for item in table}
    return sorted(list(categories)) or ["Dairy", "Produce", "Bakery", "Poultry", "Pantry", "Leftovers", "General"]


def match_food_item(name: str) -> Optional[Dict[str, Any]]:
    """
    Finds the best matching shelf-life entry for a given grocery name.
    Matches via:
      1. Exact match on food name
      2. Keyword substring matches
      3. Fuzzy string matching using rapidfuzz (if available)
    """
    table = load_shelf_life_table()
    query = name.lower().strip()

    # 1. Exact match
    for item in table:
        if query == item["food"]:
            return item

    # 2. Check if item food name is inside query or query is inside item food name
    for item in table:
        if item["food"] in query or query in item["food"]:
            return item

    # 3. Keyword check
    for item in table:
        for kw in item["keywords"]:
            if kw in query or query in kw:
                return item

    # 4. Fuzzy fallback using rapidfuzz
    try:
        from rapidfuzz import process, fuzz

        # Build list of names and keywords to match against
        candidate_map: Dict[str, Dict[str, Any]] = {}
        for item in table:
            candidate_map[item["food"]] = item
            for kw in item["keywords"]:
                candidate_map[kw] = item

        match = process.extractOne(
            query,
            list(candidate_map.keys()),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=65,
        )
        if match:
            matched_key, score, _ = match
            return candidate_map[matched_key]
    except ImportError:
        pass

    return None


def get_shelf_life_days(
    food_name: str,
    storage: str = "fridge",
    default_days: int = 7,
) -> Tuple[int, str, bool]:
    """
    Determines shelf life in days for an item and chosen storage place.
    Lookup precedence:
      1. User override table (if the user previously saved a custom duration)
      2. Shelf-life table for the specific storage place ('fridge', 'room', 'freezer')
      3. Fallback default
    Returns:
      (days: int, category: str, is_known: bool)
    """
    storage = storage.lower().strip()
    storage_col = f"{storage}_days"

    # 1. Check user override in database
    override = db.get_user_override(food_name)
    if override and override.get("shelf_days"):
        return override["shelf_days"], override.get("category", "General"), True

    # 2. Match from CSV table
    matched = match_food_item(food_name)
    if matched:
        category = matched["category"]
        days = matched.get(storage_col)
        if days is not None and days > 0:
            return days, category, True

        # Fallback to fridge days if room/freezer is not specified
        if matched.get("fridge_days"):
            return matched["fridge_days"], category, True

        return default_days, category, True

    # 3. Unknown item
    return default_days, "General", False


def calculate_estimated_expiry(
    food_name: str,
    purchase_date_str: str,
    storage: str = "fridge",
) -> Tuple[str, str, bool]:
    """
    Computes estimated expiry date = purchase_date + shelf_days.
    Returns:
      (expiry_date_iso: str, category: str, is_known_in_table: bool)
    """
    try:
        p_date = date.fromisoformat(purchase_date_str)
    except (ValueError, TypeError):
        p_date = date.today()

    days, category, is_known = get_shelf_life_days(food_name, storage)
    exp_date = p_date + timedelta(days=days)
    return exp_date.isoformat(), category, is_known


def calculate_opened_expiry(
    current_expiry_str: str,
    opened_date_str: str,
    food_name: str,
) -> str:
    """
    Implements the 'Opened-pack clock':
    When an item is opened, calculate:
      opened_expiry = opened_date + opened_fridge_days (from shelf-life table)
    The new expiry is the EARLIER of current_expiry and opened_expiry.
    CRITICAL RULE: Never extend an expiry date!
    """
    try:
        curr_exp = date.fromisoformat(current_expiry_str)
    except (ValueError, TypeError):
        curr_exp = date.today()

    try:
        open_date = date.fromisoformat(opened_date_str)
    except (ValueError, TypeError):
        open_date = date.today()

    matched = match_food_item(food_name)
    opened_fridge_days = matched.get("opened_fridge_days") if matched else None

    # If opened shelf life is known in the table
    if opened_fridge_days is not None and opened_fridge_days > 0:
        opened_exp = open_date + timedelta(days=opened_fridge_days)
        # Choose the earlier of current expiry and opened expiry
        final_exp = min(curr_exp, opened_exp)
        return final_exp.isoformat()

    # If not known, maintain current expiry (never extend)
    return curr_exp.isoformat()


def get_urgency_band(expiry_date_str: str, as_of_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Classifies an item into urgency bands based on days left until expiry:
      - RED: Expired (<0) or <= 2 days left
      - YELLOW: 3 to 5 days left
      - GREEN: > 5 days left

    Returns a dict:
      {
        "band": "RED" | "YELLOW" | "GREEN",
        "days_left": int,
        "label": str,
        "color": str (hex),
        "badge": str
      }
    """
    if as_of_date is None:
        as_of_date = date.today()

    try:
        exp_date = date.fromisoformat(expiry_date_str)
    except (ValueError, TypeError):
        exp_date = as_of_date

    days_left = (exp_date - as_of_date).days

    if days_left < 0:
        abs_days = abs(days_left)
        return {
            "band": "RED",
            "days_left": days_left,
            "label": f"Expired {abs_days}d ago",
            "color": "#EF4444",
            "badge": f"🔴 Expired ({abs_days}d ago)",
        }
    elif days_left == 0:
        return {
            "band": "RED",
            "days_left": 0,
            "label": "Expires Today",
            "color": "#EF4444",
            "badge": "🔴 Expires Today",
        }
    elif days_left <= 2:
        return {
            "band": "RED",
            "days_left": days_left,
            "label": f"{days_left}d left",
            "color": "#EF4444",
            "badge": f"🔴 {days_left} day{'s' if days_left > 1 else ''} left",
        }
    elif 3 <= days_left <= 5:
        return {
            "band": "YELLOW",
            "days_left": days_left,
            "label": f"{days_left}d left",
            "color": "#F59E0B",
            "badge": f"🟡 {days_left} days left",
        }
    else:
        return {
            "band": "GREEN",
            "days_left": days_left,
            "label": f"{days_left}d left",
            "color": "#10B981",
            "badge": f"🟢 {days_left} days left",
        }


def validate_date_string(date_str: str, reference_year: Optional[int] = None) -> Tuple[bool, str]:
    """
    Strict date validation:
      - Must be valid ISO YYYY-MM-DD
      - Reject years before 2020
      - Reject years more than 5 years ahead
    Returns:
      (is_valid: bool, error_message: str)
    """
    if not date_str or not isinstance(date_str, str):
        return False, "Date cannot be empty."

    date_str = date_str.strip()

    try:
        parsed = date.fromisoformat(date_str)
    except ValueError:
        return False, f"Invalid date format '{date_str}'. Expected YYYY-MM-DD."

    if parsed.year < 2020:
        return False, f"Date year ({parsed.year}) is invalid. Dates before 2020 are rejected."

    current_year = reference_year or date.today().year
    if parsed.year > current_year + 5:
        return False, f"Date year ({parsed.year}) is implausible. Must be within 5 years of present ({current_year + 5})."

    return True, ""


def check_date_plausibility(
    expiry_date: date,
    purchase_date: Optional[date] = None,
    max_shelf_years: int = 5,
) -> bool:
    """
    Plausibility check:
      - Year is >= 2020
      - Not more than 5 years into the future
      - Expiry is not before purchase date by more than 365 days (in case of old batch)
    """
    today = date.today()
    if expiry_date.year < 2020:
        return False
    if expiry_date.year > today.year + max_shelf_years:
        return False
    if purchase_date and (purchase_date - expiry_date).days > 365:
        return False
    return True


# List of non-food keywords to filter out receipt headers, footers, taxes, totals, etc.
NON_FOOD_KEYWORDS = {
    "total", "subtotal", "sub-total", "grand total", "net amount",
    "tax", "gst", "cgst", "sgst", "igst", "vat",
    "discount", "promo", "coupon", "savings", "saved",
    "delivery", "shipping", "handling", "platform fee", "bag fee", "tip",
    "payment", "paid", "cash", "upi", "card", "visa", "mastercard",
    "order id", "order no", "order #", "invoice", "receipt", "bill",
    "thank you", "visit again", "customer", "phone", "mobile", "address",
    "date", "time", "cashier", "terminal", "fssai", "license",
    "blinkit", "zepto", "instamart", "swiggy", "zomato", "bigbasket",
}


def is_non_food_line(line: str) -> bool:
    """
    Detects if a line from a receipt or pasted order text is a non-food artifact
    (e.g., total, tax, delivery fee, invoice number, store name).
    """
    clean = line.strip().lower()
    if not clean or len(clean) < 2:
        return True

    # If line is only numbers or symbols
    if not any(c.isalpha() for c in clean):
        return True

    # Check for direct keyword matches
    for kw in NON_FOOD_KEYWORDS:
        # Match as word boundary or exact match
        if kw in clean:
            # Avoid false positive on food items like "total milk" or similar if any
            # Typically lines with "Total: Rs 50" or "GST 5%" or "Delivery Charge"
            if clean == kw or f"{kw}:" in clean or f"{kw} " in clean or f" {kw}" in clean:
                return True

    return False


def parse_pasted_order_text(
    raw_text: str,
    default_purchase_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Parses pasted order text (e.g. from Blinkit, Zepto, Swiggy Instamart, or SMS bills).
    Extracts item names, quantities, units, and prices.
    Filters out non-food lines (totals, taxes, fees).
    Automatically matches each food item to the shelf-life table and estimates expiry dates.
    """
    import re

    if not default_purchase_date:
        default_purchase_date = date.today().isoformat()

    items: List[Dict[str, Any]] = []
    lines = raw_text.splitlines()

    for line in lines:
        raw_line = line.strip()
        if not raw_line or is_non_food_line(raw_line):
            continue

        # Extract price if present (e.g., "Rs 45", "Rs. 108.50", "₹120", "45.00")
        price: Optional[float] = None
        price_match = re.search(r"(?:rs\.?|inr|₹)\s*(\d+(?:\.\d{1,2})?)", raw_line, re.IGNORECASE)
        if not price_match:
            # Check trailing numbers like "... 45.00"
            price_match = re.search(r"(?:\s+|-|:)\s*(\d+(?:\.\d{1,2})?)$", raw_line)

        if price_match:
            try:
                price = float(price_match.group(1))
            except ValueError:
                price = None

        # Clean line to find item name and quantity
        cleaned = raw_line
        if price_match:
            cleaned = cleaned[:price_match.start()] + cleaned[price_match.end():]

        # Extract quantity and unit (e.g., "500g", "1 kg", "2 L", "1 pack", "2 pcs", "x 2")
        qty = 1.0
        unit = "pack"

        # Check for multiplier like "x 2" or "2x" or "qty: 2"
        multiplier_match = re.search(r"(?:x\s*(\d+)|(\d+)\s*x|qty:\s*(\d+))", cleaned, re.IGNORECASE)
        if multiplier_match:
            for g in multiplier_match.groups():
                if g:
                    qty = float(g)
                    break
            cleaned = cleaned[:multiplier_match.start()] + cleaned[multiplier_match.end():]

        # Check for unit patterns: kg, g, l, ml, pcs, packet, bunch
        unit_match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|l|ml|litre|litres|pcs|pieces|pack|packet|bunch|dozen|loaf|cup)", cleaned, re.IGNORECASE)
        if unit_match:
            qty = float(unit_match.group(1))
            unit = unit_match.group(2).lower()
            cleaned = cleaned[:unit_match.start()] + cleaned[unit_match.end():]

        # Clean remaining text for food name
        item_name = re.sub(r"[-–—•\t\(\)]", " ", cleaned).strip()
        item_name = re.sub(r"\s+", " ", item_name).strip()

        # If name became too short or blank, skip
        if len(item_name) < 2:
            continue

        # Estimate shelf life & expiry
        # Default storage: check category default or standard heuristic
        matched = match_food_item(item_name)
        if matched:
            category = matched["category"]
            is_matched = True
        else:
            category = "General"
            is_matched = False

        # Get default storage setting
        def_storage = db.get_setting(f"storage_default_{category}", default="fridge" if category in ("Dairy", "Produce", "Meat") else "room")

        exp_date, cat, is_known = calculate_estimated_expiry(
            food_name=item_name,
            purchase_date_str=default_purchase_date,
            storage=def_storage,
        )

        items.append({
            "name": item_name.title(),
            "category": cat,
            "quantity": qty,
            "unit": unit,
            "price": price,
            "storage": def_storage,
            "purchase_date": default_purchase_date,
            "expiry_date": exp_date,
            "date_source": "estimated",
            "is_matched": is_matched or is_known,
        })

    return items

