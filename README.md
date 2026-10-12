# 🥑 GrocoPilot — Smart Food Expiry & Kitchen Waste Assistant

> **"Never let groceries go to waste. Eat fresh, use what spoils first."**
> 
> *Built for college hackathons using Python 3.10+, Streamlit, SQLite, and Google Gemini Vision AI.*

---

## 🎯 The Problem
Working professionals and urban families buy groceries in bulk (via quick-commerce apps like *Blinkit, Zepto, Swiggy Instamart, BigBasket* or local supermarkets). Food gets stashed away in refrigerator drawers and pantry shelves, where it quietly expires unnoticed.

Existing food expiry trackers fail because they demand tedious manual typing for every single tomato, bread packet, or milk pouch. **GrocoPilot solves this with minimal friction:**
1. **Zero-effort inventory building**: Paste delivery app summaries or upload receipt screenshots.
2. **One-tap AI pack label scanning**: Point your phone camera at a package label to read printed expiry and manufacturing dates using **Google Gemini Vision Flash**.
3. **Smart Urgency Bands**: Color-coded categorization (🔴 RED $\le 2$ days or expired, 🟡 YELLOW 3–5 days, 🟢 GREEN $>5$ days).
4. **Opened-Pack Clock**: Opening a milk pouch or loaf of bread reduces its lifespan immediately without ever extending past its original expiry.
5. **AI Recipe Rescue Engine**: Crafts 3 practical, home-style Indian recipes using ingredients that are about to spoil, preventing food from hitting the garbage bin.
6. **Honest Waste & Financial Savings Accounting**: Calculates exact rupees saved and lost without ever guessing missing prices.

---

## 🎨 Color Palette & Design
GrocoPilot uses a tailored wholesome color palette inspired by fresh earth and pantry ingredients:
- **🌿 Sage Green (`#749563`)**: Fresh produce, safe groceries, verified status, and primary action buttons.
- **🧱 Brick Red (`#B82C35`)**: Urgent items ($\le 2$ days or expired), waste warnings, and discard indicators.
- **🍊 Warm Tangerine (`#F7893B`)**: Attention zone (3–5 days left) and safety callouts.
- **🧈 Buttercream Pale Cream (`#FDF2A9`)**: Card highlights, soft badges, and welcoming accents.

---

## 📁 Project Architecture & File Structure

```text
GrocoPilot/
├── app.py              # Streamlit entry point, wholesome styling, animations, and page routing
├── db.py               # SQLite schema (items, user_overrides, settings) and CRUD queries
├── logic.py            # Shelf-life lookup, opened-pack clock, urgency bands, non-food filter, and date validation
├── scanner.py          # Google Gemini Flash Vision AI: receipt OCR, label date parsing, produce detection
├── recipes.py          # AI & offline recipe generator using near-expiry ingredients
├── data/
│   ├── shelf_life.csv  # 35+ Indian household foods with conservative shelf lives and opened days
│   └── recipes.json    # Curated offline Indian home-style recipes database
├── tests/
│   ├── test_logic.py   # Unit tests for urgency bands, clock arithmetic, text parsing, and date limits
│   ├── test_scanner.py # Unit tests for image preprocessing, fallback safety, and date arithmetic
│   ├── test_recipes.py # Unit tests for recipe filtering, urgency sorting, and offline matching
│   └── test_db.py      # Unit tests for honest waste valuation and settings persistence
├── requirements.txt    # Project dependencies
└── README.md           # Setup, hackathon explanation, and documentation
```

---

## ⚡ Quick Start Guide (For Beginners)

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12 installed on your system.

### 2. Clone / Open the Workspace
```powershell
cd c:\Users\Dhyey\Documents\GrocoPilot
```

### 3. Create & Activate a Virtual Environment
```powershell
# Using Python's built-in venv:
python -m venv .venv
.venv\Scripts\activate

# Or using uv (ultra-fast):
uv venv --python 3.12 .venv
.venv\Scripts\activate
```

### 4. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 5. Set Your Google Gemini API Key (Optional but Recommended)
Get a free API key from [Google AI Studio](https://aistudio.google.com/):
```powershell
# In PowerShell (Windows):
$env:GEMINI_API_KEY="your_actual_gemini_api_key_here"

# In Bash / macOS / Linux:
export GEMINI_API_KEY="your_actual_gemini_api_key_here"
```
*(Note: If you do not have an API key, GrocoPilot automatically activates **Smart Offline Mode**. Bill text parsing, autocomplete quick-add, and offline recipe suggestions continue to work 100% without crashing!)*

### 6. Run GrocoPilot
```powershell
streamlit run app.py
```
Open **[http://localhost:8501](http://localhost:8501)** in your web browser.

---

## 🧪 Running the Unit Tests

We have written **25 unit tests** with `pytest` covering all business logic, arithmetic rules, and safety boundaries:
```powershell
.venv\Scripts\python.exe -m pytest -v
```
You should see:
```text
============================= 25 passed in 0.35s =============================
```

---

## 🏆 How to Present to Hackathon Judges (Pitch & Demo Script)

1. **Step 1: Open the Dashboard**
   - Click **"🚀 Load 8 Demo Items"** (in Settings or empty state).
   - Point out the **Header Metrics** and the **Urgency Groupings**:
     - 🔴 **Immediate Attention**: Items expired or expiring within 48 hours (*Amul Toned Milk, Fresh Palak, Malai Paneer*).
     - 🟡 **Use Soon**: Items expiring in 3–5 days (*Brown Bread, Tomatoes*).
     - 🟢 **Safe**: Items good for over a week (*Greek Yogurt, Eggs, Basmati Rice*).

2. **Step 2: Demonstrate the "Opened-Pack Clock"**
   - Show *Amul Toned Milk* or *Brown Bread*.
   - Tap **"📦 Open"**.
   - Explain: *"When you open a sealed packet, air and bacteria enter. GrocoPilot reduces the expiry date to $\min(\text{current\_expiry}, \text{today} + \text{opened\_fridge\_days})$. Crucially, it **never extends an expiry date**!"*

3. **Step 3: Show Frictionless Bill Parsing**
   - Navigate to **"➕ Add Items"** -> **"📝 Paste Order Text"**.
   - Click **"📋 Load Sample Blinkit / Zepto Bill"** and tap **"🔍 Parse & Review Items"**.
   - Show how intelligent regex filtering automatically strips out noise (*Subtotals, Delivery fees, Taxes, Platform charges*) and prepares an editable staging table (`st.data_editor`) where nothing is saved until the user clicks **"💾 Save to My Fridge"**.

4. **Step 4: Demonstrate AI Label Scanning**
   - On any item row on the Dashboard, click **"✨ AI Scan"**.
   - Show how Gemini Flash Vision reads the printed packaging date, calculates the last day of the month if day is omitted, validates plausibility ($\ge 2020$), and lets the user confirm with one tap.

5. **Step 5: Demonstrate the Recipe Rescue Engine**
   - Navigate to **"🍳 Recipes"**.
   - Point out how the app prioritizes ingredients with the fewest days left.
   - Click **"✨ Generate AI Chef Recipes"** to show 3 tailored home-style Indian meals that utilize what's about to spoil.

6. **Step 6: Show Honest Waste Accounting**
   - Navigate to **"📊 Waste & Savings"**.
   - Highlight the **Rescue Efficiency Rate** and explain: *"Our accounting is strictly honest: we only count prices that were actually known from receipts or user input. We never guess missing values."*

---

## 🔒 Privacy & Safety Notice

- **Photo In-Memory Processing**: Photos uploaded or taken with camera inputs are held strictly in memory (`io.BytesIO`), resized to max $1400\text{px}$, and discarded immediately after AI inference. No user photos are ever saved to disk.
- **Privacy Notice on Scan Screens**: *"Photos are sent to an AI service for reading and are not stored by this app. Avoid including personal details in the frame."* Check your provider's terms of service and rate limits.
- **Food Safety Disclaimer**:
  > *"GrocoPilot is a reminder tool, not a food-safety checker. Dates are estimates unless marked Verified. Always check the pack and use your senses. Do not eat anything that looks, smells, or tastes off."*
  GrocoPilot never declares an item "safe to eat"; expired food is flagged to *"check or discard"*.

---

## ⚠️ Known Limitations
1. **Crumpled or Smudged Receipts**: Very faded thermal receipts or handwritten local kirana chits may require manual quantity correction in the review table.
2. **Regional Packaging Date Formats**: While Indian labels typically follow `DD/MM/YYYY` or `MM/YYYY`, imported products may use `MM/DD/YYYY`. Users can easily adjust detected dates via the `✏️ Edit Date` button.
3. **Free-Tier API Rate Limits**: High-frequency scanning on Google Gemini free tier can hit RPM (requests per minute) limits. GrocoPilot includes a session API call counter and graceful offline fallback to handle this smoothly.

---

*Made with ❤️ for food rescue and smarter kitchens.*
