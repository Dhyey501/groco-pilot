"""
scanner.py - Vision AI scanning for receipts, food labels, and front packs.
--------------------------------------------------------------------------
This module uses Google's Gemini API via the `google-genai` Python SDK
to visually inspect receipts and grocery packs.

Key Architectural Guarantees:
  1. Zero Disk Storage: Photos are processed in memory and discarded.
  2. In-Memory Resizing: Longest side capped at 1400px to optimize tokens/speed.
  3. Image Hash Caching: Avoids re-calling the API if the exact same image is uploaded twice.
  4. Robust Error Handling: Never crashes; returns a dict with 'status' ('ok' | 'failed' | 'no_date' | 'implausible').
  5. Privacy & Cleanliness: Ignores totals, taxes, store details, and personal info.
  6. Rate Limit Protection: Tracks session API calls and alerts users before hitting free tier limits.
"""

from __future__ import annotations
import calendar
from datetime import date
from dateutil.relativedelta import relativedelta
import hashlib
import io
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image

import logic

# =====================================================================
# GEMINI MODEL CONFIGURATION
# Copy the current vision-capable Flash model name from Google AI Studio.
# e.g., 'gemini-3.8-flash' or 'gemini-2.5-flash'
# =====================================================================
MODEL = "gemini-3.8-flash"

# Session state cache for processed images: sha256 -> response_dict
_IMAGE_CACHE: Dict[str, Dict[str, Any]] = {}


def clear_image_cache() -> None:
    """Clears the in-memory processed image cache."""
    global _IMAGE_CACHE
    _IMAGE_CACHE.clear()


# Session counter for API calls to guard against free tier exhaustion
_API_CALL_COUNT: int = 0
API_CALL_WARNING_THRESHOLD: int = 15


def get_api_call_count() -> int:
    """Returns the total number of Gemini API calls made in the current session."""
    global _API_CALL_COUNT
    return _API_CALL_COUNT


def increment_api_call_count() -> int:
    """Increments and returns the session API call counter."""
    global _API_CALL_COUNT
    _API_CALL_COUNT += 1
    return _API_CALL_COUNT


def get_gemini_client() -> Optional[Any]:
    """
    Initializes and returns the google-genai Client using GEMINI_API_KEY.
    Returns None if the key is missing or SDK is unavailable.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        try:
            import streamlit as st
            api_key = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
        except Exception:
            pass

    if not api_key:
        return None

    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def preprocess_image(image_input: Union[bytes, io.BytesIO, Image.Image]) -> Tuple[bytes, str]:
    """
    Standardizes any input image:
      1. Converts to PIL Image (handling PNG, WebP, JPEG, HEIC).
      2. Converts RGBA/P to RGB.
      3. Resizes so the longest dimension is at most 1400px (preserving aspect ratio).
      4. Exports as JPEG bytes in memory (no disk writing).
      5. Generates a SHA-256 hash for caching.
    """
    if isinstance(image_input, bytes):
        pil_img = Image.open(io.BytesIO(image_input))
    elif isinstance(image_input, io.BytesIO):
        image_input.seek(0)
        pil_img = Image.open(image_input)
    elif isinstance(image_input, Image.Image):
        pil_img = image_input
    else:
        # Fallback for uploaded file objects
        image_input.seek(0)
        pil_img = Image.open(image_input)

    # Convert to RGB mode if needed
    if pil_img.mode in ("RGBA", "P", "LA"):
        pil_img = pil_img.convert("RGB")

    # Resize if longest edge exceeds 1400px
    max_dim = 1400
    w, h = pil_img.size
    longest = max(w, h)
    if longest > max_dim:
        scale = max_dim / float(longest)
        new_size = (int(w * scale), int(h * scale))
        pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)

    # Compress to in-memory JPEG bytes
    buffer = io.BytesIO()
    pil_img.save(buffer, format="JPEG", quality=85, optimize=True)
    jpeg_bytes = buffer.getvalue()

    # Calculate SHA-256 hash
    sha256 = hashlib.sha256(jpeg_bytes).hexdigest()
    return jpeg_bytes, sha256


def call_gemini_vision(
    prompt: str,
    jpeg_bytes: bytes,
    timeout_seconds: int = 25,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Calls the Gemini API with an image and text prompt requesting JSON output.
    Retries ONCE on failure.
    Returns:
      (success: bool, raw_json_text: Optional[str], error_message: Optional[str])
    """
    client = get_gemini_client()
    if not client:
        return False, None, "GEMINI_API_KEY environment variable is not set. Please set your Gemini API key."

    from google.genai import types

    # Prepare inline JPEG part
    image_part = types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")

    # Retry once on failure
    last_error = ""
    for attempt in range(2):
        try:
            increment_api_call_count()
            response = client.models.generate_content(
                model=MODEL,
                contents=[prompt, image_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,  # Low temperature for strict factual reading
                ),
            )
            if response and response.text:
                return True, response.text.strip(), None
            else:
                last_error = "Empty response received from Gemini API."
        except Exception as e:
            last_error = str(e)
            time.sleep(1)  # Brief pause before single retry

    return False, None, f"AI Vision scanning failed after retry: {last_error}"


def scan_receipt(
    image_input: Any,
    default_purchase_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extracts grocery line items from a receipt or supermarket bill screenshot.
    Rules:
      - Extracts ONLY food and drink items.
      - Ignores totals, taxes, delivery fees, store details, and ANY personal information.
      - Matches each name to shelf-life table and estimates expiry dates.
    Returns:
      {
        "status": "ok" | "failed",
        "items": List[Dict[str, Any]],
        "error": Optional[str],
        "api_calls": int
      }
    """
    if not default_purchase_date:
        default_purchase_date = date.today().isoformat()

    try:
        jpeg_bytes, img_hash = preprocess_image(image_input)
    except Exception as e:
        return {"status": "failed", "items": [], "error": f"Failed to process image: {str(e)}", "api_calls": get_api_call_count()}

    # Check cache
    cache_key = f"receipt_{img_hash}"
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]

    prompt = """
    You are an expert grocery receipt parser.
    Examine the provided image of a grocery receipt, supermarket invoice, or grocery app order screenshot.
    
    CRITICAL PRIVACY & CONTENT RULES:
    1. Extract ONLY food and drink items.
    2. Completely IGNORE:
       - Totals, Subtotals, Discounts, Taxes, GST, Delivery fees, Packaging charges.
       - Store names, addresses, phone numbers, invoice/order IDs, cashier names.
       - ANY personal names or sensitive information.
    3. For each food item, extract:
       - "name": Clean product name (e.g. "Amul Toned Milk", "Brown Bread", "Tomatoes").
       - "quantity": Number of units bought (float or null if unclear, default 1.0).
       - "unit": Unit of measurement (e.g. "kg", "g", "L", "ml", "pack", "bunch", "pcs", or null).
       - "price": Price paid for that item as a float (null if not clearly legible).
    4. Never invent items. If not sure, use null.
    
    Output strictly valid JSON matching this schema:
    {
      "items": [
        {
          "name": "string",
          "quantity": 1.0,
          "unit": "pack",
          "price": 45.0
        }
      ]
    }
    """

    success, raw_json, err = call_gemini_vision(prompt, jpeg_bytes)
    if not success or not raw_json:
        res = {"status": "failed", "items": [], "error": err or "Failed to read receipt.", "api_calls": get_api_call_count()}
        return res

    try:
        parsed_data = json.loads(raw_json)
        raw_items = parsed_data.get("items", [])
    except json.JSONDecodeError:
        return {"status": "failed", "items": [], "error": "AI returned invalid JSON format.", "api_calls": get_api_call_count()}

    # Normalize items and match with shelf-life database
    processed_items: List[Dict[str, Any]] = []
    for item in raw_items:
        name = str(item.get("name") or "").strip()
        if not name or logic.is_non_food_line(name):
            continue

        try:
            qty = float(item.get("quantity") or 1.0)
        except (ValueError, TypeError):
            qty = 1.0

        unit = str(item.get("unit") or "pack").strip()

        price_val = item.get("price")
        price = float(price_val) if price_val is not None and isinstance(price_val, (int, float)) and price_val > 0 else None

        # Match against shelf-life table
        matched = logic.match_food_item(name)
        if matched:
            category = matched["category"]
            is_matched = True
        else:
            category = "General"
            is_matched = False

        # Calculate estimated expiry
        exp_date, cat, is_known = logic.calculate_estimated_expiry(
            food_name=name,
            purchase_date_str=default_purchase_date,
            storage="fridge",
        )

        processed_items.append({
            "name": name.title(),
            "category": cat,
            "quantity": qty,
            "unit": unit,
            "price": price,
            "storage": "fridge" if cat in ("Dairy", "Produce", "Meat") else "room",
            "purchase_date": default_purchase_date,
            "expiry_date": exp_date,
            "date_source": "estimated",
            "is_matched": is_matched or is_known,
        })

    result = {
        "status": "ok",
        "items": processed_items,
        "error": None,
        "api_calls": get_api_call_count(),
    }
    _IMAGE_CACHE[cache_key] = result
    return result


def identify_front(image_input: Any) -> Dict[str, Any]:
    """
    Identifies a single food item from a photo of its front packaging or loose produce.
    Category MUST be one of the categories in shelf_life.csv.
    Used when there is no receipt.
    Returns:
      {"status": "ok"|"failed", "name": str, "category": str, "error": Optional[str]}
    """
    try:
        jpeg_bytes, img_hash = preprocess_image(image_input)
    except Exception as e:
        return {"status": "failed", "name": "", "category": "General", "error": f"Image error: {str(e)}"}

    cache_key = f"front_{img_hash}"
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]

    allowed_categories = logic.get_all_categories()
    cat_list_str = ", ".join(f'"{c}"' for c in allowed_categories)

    prompt = f"""
    You are an expert Indian grocery classifier.
    Look at this image of a grocery product or loose produce (fruits, vegetables, pantry grain, dairy, etc.).
    
    RULES:
    1. Identify the specific food name (e.g. "Amul Milk", "Spinach", "Basmati Rice", "Eggs").
    2. Choose the single most appropriate category from ONLY this exact list:
       [{cat_list_str}]
    3. Return strictly JSON:
       {{
         "name": "Product Name",
         "category": "Exact Category From List"
       }}
    """

    success, raw_json, err = call_gemini_vision(prompt, jpeg_bytes)
    if not success or not raw_json:
        return {"status": "failed", "name": "", "category": "General", "error": err or "Failed to identify item."}

    try:
        data = json.loads(raw_json)
        name = str(data.get("name", "Unknown Food")).strip()
        cat = str(data.get("category", "General")).strip()
        if cat not in allowed_categories:
            cat = "General"

        result = {
            "status": "ok",
            "name": name,
            "category": cat,
            "error": None,
        }
        _IMAGE_CACHE[cache_key] = result
        return result
    except json.JSONDecodeError:
        return {"status": "failed", "name": "", "category": "General", "error": "Invalid AI response format."}


def scan_label(image_input: Any) -> Dict[str, Any]:
    """
    Reads the BACK label of a packaged food product for printed dates.
    Extracts:
      - expiry date (day, month, year)
      - manufacture date (day, month, year)
      - best_before_months
      - use_within_days_after_opening
      - raw_date_text
      - confidence ('high'|'medium'|'low')
      
    AI only READS what is printed.
    All date arithmetic is computed in Python:
      - If only month and year given: sets to the LAST day of that month.
      - If manufacture date and best_before_months given: calculates with dateutil.relativedelta.
      - Validates against plausibility checks.
      
    Returns dict with status: 'ok' | 'no_date' | 'implausible' | 'failed'
    """
    try:
        jpeg_bytes, img_hash = preprocess_image(image_input)
    except Exception as e:
        return {"status": "failed", "error": f"Image processing error: {str(e)}"}

    cache_key = f"label_{img_hash}"
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]

    prompt = """
    You are an expert food packaging reader specializing in Indian product labels.
    Look at the back/side label of this food package.
    
    CRITICAL INSTRUCTIONS:
    - Only report what is clearly and explicitly printed. NEVER guess or calculate.
    - If a field is not printed or is illegible, set it to null.
    - Indian labels usually print dates in Day/Month/Year or Month/Year format (e.g. 15/08/2026 or AUG 2026).
    - Always output 4-digit years.
    - Completely ignore batch numbers, lot numbers, MRP prices, and FSSAI license numbers.
    
    Output strictly valid JSON with this exact schema:
    {
      "product_name": "string or null",
      "expiry": {
        "day": 15,
        "month": 8,
        "year": 2026
      },
      "manufacture": {
        "day": 10,
        "month": 2,
        "year": 2026
      },
      "best_before_months": null,
      "use_within_days_after_opening": null,
      "raw_date_text": "e.g. USE BY 15/08/26",
      "confidence": "high"
    }
    Note: "expiry" and "manufacture" can have null for day if only month/year is shown.
    If no dates are found at all, return null for expiry, manufacture, and best_before_months.
    """

    success, raw_json, err = call_gemini_vision(prompt, jpeg_bytes)
    if not success or not raw_json:
        return {"status": "failed", "error": err or "Failed to read label image."}

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return {"status": "failed", "error": "AI returned invalid JSON format."}

    # Python date arithmetic & normalization
    exp_dict = data.get("expiry")
    mfg_dict = data.get("manufacture")
    bb_months = data.get("best_before_months")
    raw_date_text = data.get("raw_date_text")

    computed_expiry_date: Optional[date] = None

    # Case 1: Direct expiry date printed
    if exp_dict and isinstance(exp_dict, dict) and exp_dict.get("year"):
        try:
            year = int(exp_dict["year"])
            month = int(exp_dict.get("month") or 1)
            # Two-digit year safeguard
            if year < 100:
                year += 2000

            # If day is given
            if exp_dict.get("day"):
                day = int(exp_dict["day"])
            else:
                # If only month and year given: use LAST day of that month
                _, last_day = calendar.monthrange(year, month)
                day = last_day

            computed_expiry_date = date(year, month, day)
        except (ValueError, TypeError):
            computed_expiry_date = None

    # Case 2: Only manufacture date and "best before N months" printed
    if not computed_expiry_date and mfg_dict and isinstance(mfg_dict, dict) and mfg_dict.get("year") and bb_months:
        try:
            mfg_year = int(mfg_dict["year"])
            if mfg_year < 100:
                mfg_year += 2000
            mfg_month = int(mfg_dict.get("month") or 1)
            mfg_day = int(mfg_dict.get("day") or 1)
            mfg_date = date(mfg_year, mfg_month, mfg_day)

            # Compute with dateutil.relativedelta
            computed_expiry_date = mfg_date + relativedelta(months=int(bb_months))
        except (ValueError, TypeError):
            computed_expiry_date = None

    # Check status
    if not computed_expiry_date:
        res = {
            "status": "no_date",
            "product_name": data.get("product_name"),
            "raw_date_text": raw_date_text,
            "error": "No clear expiry date or 'best before' period could be read from the label.",
        }
        _IMAGE_CACHE[cache_key] = res
        return res

    # Run plausibility check from logic.py
    if not logic.check_date_plausibility(computed_expiry_date):
        res = {
            "status": "implausible",
            "detected_date": computed_expiry_date.isoformat(),
            "raw_date_text": raw_date_text,
            "error": f"Detected date '{computed_expiry_date.isoformat()}' appears implausible (outside 2020-2031 window).",
        }
        _IMAGE_CACHE[cache_key] = res
        return res

    # Success
    res = {
        "status": "ok",
        "product_name": data.get("product_name"),
        "detected_date": computed_expiry_date.isoformat(),
        "raw_date_text": raw_date_text,
        "confidence": data.get("confidence", "medium"),
        "use_within_days_after_opening": data.get("use_within_days_after_opening"),
        "error": None,
    }
    _IMAGE_CACHE[cache_key] = res
    return res


def scan_grocery_pack_and_expiry(
    image_input: Any,
    purchase_date_str: Optional[str] = None,
) -> Dict[str, Any]:
    """
    All-in-one Quick Vision AI scanner for a grocery package (front or back label).
    Quickly identifies:
      1. Product name and brand (e.g. 'Amul Taaza Milk', 'Harvest Gold Bread').
      2. Category (from allowed shelf-life categories).
      3. Quantity and unit (e.g. 500 ml, 1 pack, 250 g).
      4. Exact printed expiry date or calculates from manufacture date + best before months.
      5. Storage recommendation ('fridge', 'room', or 'freezer').

    If an exact printed expiry date is visible and legible, date_source is 'scanned' (Verified).
    If no printed date is visible (e.g. front face only), it safely falls back to conservative
    estimated expiry from our Indian shelf life database and marks date_source as 'estimated'.

    Returns:
      {
        "status": "ok" | "failed",
        "item": Dict[str, Any],
        "has_printed_expiry": bool,
        "raw_date_text": Optional[str],
        "error": Optional[str],
        "api_calls": int
      }
    """
    if not purchase_date_str:
        purchase_date_str = date.today().isoformat()

    try:
        jpeg_bytes, img_hash = preprocess_image(image_input)
    except Exception as e:
        return {
            "status": "failed",
            "item": None,
            "has_printed_expiry": False,
            "raw_date_text": None,
            "error": f"Image processing error: {str(e)}",
            "api_calls": get_api_call_count(),
        }

    cache_key = f"quick_pack_{img_hash}"
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]

    allowed_cats = logic.get_all_categories()
    cat_list_str = ", ".join(f'"{c}"' for c in allowed_cats)

    prompt = f"""
    You are an expert Indian grocery product identifier and label reader.
    Analyze the provided image of a grocery package, food carton, pouch, can, or container.

    GOAL:
    Extract the product identity AND any printed expiry/manufacturing dates in one pass.

    RULES:
    1. "name": Specific product name with brand (e.g. "Amul Taaza Toned Milk", "Modern Brown Bread", "Dahi", "Kissan Tomato Ketchup").
    2. "category": Choose ONLY from this list: [{cat_list_str}]. If unsure, choose "General".
    3. "quantity": Numerical quantity (e.g. 1.0, 500, 250). If unsure, use 1.0.
    4. "unit": Unit of measurement (e.g. "pack", "ml", "L", "g", "kg", "pcs").
    5. "storage": Recommended storage ("fridge", "room", or "freezer").
    6. "expiry": If an expiry or use-by date is clearly printed, extract:
       - "day": integer or null (if only month/year is shown)
       - "month": integer 1-12 or null
       - "year": 4-digit integer or null
    7. "manufacture": If manufacture or packed date is printed:
       - "day": integer or null
       - "month": integer 1-12 or null
       - "year": 4-digit integer or null
    8. "best_before_months": integer months (e.g. if 'Best before 6 months from packaging' is printed), else null.
    9. "raw_date_text": Quote the exact date text printed on the pack (e.g. 'USE BY 18/10/26'), else null.

    Output strictly valid JSON with this exact schema:
    {{
      "name": "Product Name",
      "category": "Category",
      "quantity": 1.0,
      "unit": "pack",
      "storage": "fridge",
      "expiry": {{
        "day": 18,
        "month": 10,
        "year": 2026
      }},
      "manufacture": null,
      "best_before_months": null,
      "raw_date_text": "USE BY 18/10/26"
    }}
    If no dates are printed at all, set expiry, manufacture, best_before_months, and raw_date_text to null.
    """

    success, raw_json, err = call_gemini_vision(prompt, jpeg_bytes)
    if not success or not raw_json:
        return {
            "status": "failed",
            "item": None,
            "has_printed_expiry": False,
            "raw_date_text": None,
            "error": err or "Failed to read product package.",
            "api_calls": get_api_call_count(),
        }

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return {
            "status": "failed",
            "item": None,
            "has_printed_expiry": False,
            "raw_date_text": None,
            "error": "AI returned invalid JSON format.",
            "api_calls": get_api_call_count(),
        }

    # Extract fields
    name = str(data.get("name") or "Packaged Grocery").strip()
    category = str(data.get("category") or "General").strip()
    if category not in allowed_cats:
        matched = logic.match_food_item(name)
        category = matched["category"] if matched else "General"

    try:
        qty = float(data.get("quantity") or 1.0)
    except (ValueError, TypeError):
        qty = 1.0

    unit = str(data.get("unit") or "pack").strip()
    storage = str(data.get("storage") or ("fridge" if category in ("Dairy", "Produce", "Meat") else "room")).strip()
    if storage not in ("fridge", "room", "freezer"):
        storage = "fridge" if category in ("Dairy", "Produce", "Meat") else "room"

    raw_date_text = data.get("raw_date_text")
    exp_dict = data.get("expiry")
    mfg_dict = data.get("manufacture")
    bb_months = data.get("best_before_months")

    computed_expiry_date: Optional[date] = None

    # 1. Direct printed expiry
    if exp_dict and isinstance(exp_dict, dict) and exp_dict.get("year"):
        try:
            year = int(exp_dict["year"])
            if year < 100:
                year += 2000
            month = int(exp_dict.get("month") or 1)
            if exp_dict.get("day"):
                day = int(exp_dict["day"])
            else:
                _, last_day = calendar.monthrange(year, month)
                day = last_day
            computed_expiry_date = date(year, month, day)
        except (ValueError, TypeError):
            computed_expiry_date = None

    # 2. Manufacture date + best before months
    if not computed_expiry_date and mfg_dict and isinstance(mfg_dict, dict) and mfg_dict.get("year") and bb_months:
        try:
            mfg_year = int(mfg_dict["year"])
            if mfg_year < 100:
                mfg_year += 2000
            mfg_month = int(mfg_dict.get("month") or 1)
            mfg_day = int(mfg_dict.get("day") or 1)
            mfg_date = date(mfg_year, mfg_month, mfg_day)
            computed_expiry_date = mfg_date + relativedelta(months=int(bb_months))
        except (ValueError, TypeError):
            computed_expiry_date = None

    # Check plausibility if date was found
    has_printed = False
    if computed_expiry_date and logic.check_date_plausibility(computed_expiry_date):
        final_expiry_str = computed_expiry_date.isoformat()
        date_source = "scanned"
        has_printed = True
    else:
        # Fallback to conservative estimate from shelf life database
        final_expiry_str, cat_est, _ = logic.calculate_estimated_expiry(
            food_name=name,
            purchase_date_str=purchase_date_str,
            storage=storage,
        )
        date_source = "estimated"

    final_item = {
        "name": name.title(),
        "category": category,
        "quantity": qty,
        "unit": unit,
        "price": None,
        "storage": storage,
        "purchase_date": purchase_date_str,
        "expiry_date": final_expiry_str,
        "date_source": date_source,
        "is_matched": True,
    }

    result = {
        "status": "ok",
        "item": final_item,
        "has_printed_expiry": has_printed,
        "raw_date_text": raw_date_text,
        "error": None,
        "api_calls": get_api_call_count(),
    }
    _IMAGE_CACHE[cache_key] = result
    return result

