"""
app.py - Main entry point and page router for GrocoPilot.
---------------------------------------------------------
A smart food-expiry tracker built for working professionals and families.
Reduces manual effort by organizing groceries by urgency, applying an
opened-pack clock, and helping you use what will spoil first.
"""

import base64
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List
import streamlit as st

import db
import logic
import recipes
import scanner

def get_logo_base64() -> str:
    """Returns the base64-encoded string of the official GrocoPilot logo for HTML embedding."""
    p = Path("assets/logo.png")
    if p.exists():
        return base64.b64encode(p.read_bytes()).decode()
    return ""

# 1. Page Configuration
st.set_page_config(
    page_title="GrocoPilot | Smart Grocery Expiry Assistant",
    page_icon="assets/logo.png" if Path("assets/logo.png").exists() else "🥬",
    layout="wide",
    initial_sidebar_state="auto",
)

# 2. Database Initialization
db.init_db()

# 3. Custom CSS with Wholesome Color Palette & Dynamic Motion
st.markdown(
    """
    <style>
    /* -------------------------------------------------------------
       WHOLESOME PALETTE:
       --sage-green:      #749563 (Earthy Fresh Herbs & Green Veggies)
       --brick-red:       #B82C35 (Ripe Indian Tomatoes & Urgent Alert)
       --warm-orange:     #F7893B (Sweet Tangerine & Warning)
       --butter-cream:    #FDF2A9 (Warm Ghee & Buttercream Accent)
       --bg-warm:         #FAF8F2 (Cozy Warm Linen Canvas)
       --card-bg:         #FFFFFF (Crisp Porcelain Card Surface)
       ------------------------------------------------------------- */
    :root {
        --sage-green: #749563;
        --sage-green-dark: #526B45;
        --sage-green-light: #F0F5EC;
        --brick-red: #B82C35;
        --brick-red-light: #FDF2F2;
        --warm-orange: #F7893B;
        --warm-orange-light: #FEF4ED;
        --butter-cream: #FDF2A9;
        --butter-cream-subtle: #FFFDF4;
        --text-dark: #262C22;
        --text-muted: #555E4E;
    }

    /* Entire app warm wholesome canvas */
    .stApp, body {
        background-color: #FAF8F2 !important;
        color: #262C22 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #F3EFE4 !important;
        border-right: 1px solid #E6E1D4 !important;
    }
    [data-testid="stSidebar"] * {
        color: #262C22 !important;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #262C22 !important;
        font-weight: 700 !important;
    }

    /* Suppress spurious connection status overlay in headless previews */
    [data-testid="stConnectionStatus"], div[data-testid="stStatusWidget"] {
        display: none !important;
    }

    /* Clean container styling */
    .main .block-container {

        padding-top: 1.5rem;
        padding-bottom: 3.5rem;
        max-width: 1100px;
    }

    /* Dynamic Button Animations & Colors */
    button[kind="primary"] {
        background: linear-gradient(135deg, #749563 0%, #526B45 100%) !important;
        border: none !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        box-shadow: 0 2px 6px rgba(116, 149, 99, 0.25) !important;
    }
    button[kind="primary"]:hover {
        transform: translateY(-2px) scale(1.01) !important;
        box-shadow: 0 6px 18px rgba(116, 149, 99, 0.42) !important;
    }
    button[kind="primary"]:active {
        transform: translateY(0px) scale(0.99) !important;
    }

    /* Standard interactive buttons */
    button:not([kind="primary"]) {
        border-radius: 9px !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    button:not([kind="primary"]):hover {
        transform: translateY(-1.5px) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.07) !important;
    }

    /* Badges with Wholesome Palette */
    .badge-verified {
        background-color: #F0F5EC;
        color: #526B45;
        border: 1px solid #749563;
        padding: 3px 9px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        display: inline-block;
        box-shadow: 0 1px 3px rgba(116, 149, 99, 0.15);
    }
    .badge-estimated {
        background-color: #FEF4ED;
        color: #D36517;
        border: 1px solid #F7893B;
        padding: 3px 9px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        display: inline-block;
    }
    .badge-opened {
        background-color: #FFFDF4;
        color: #B45309;
        border: 1px solid #FDF2A9;
        padding: 3px 9px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        display: inline-block;
    }
    .badge-storage {
        background-color: #F3EFE4;
        color: #4B5563;
        padding: 3px 8px;
        border-radius: 7px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* Safety & Honesty Banner */
    .safety-notice {
        background-color: #FFFDF4;
        border-left: 5px solid #F7893B;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 0.85rem;
        color: #7C2D12;
        margin-bottom: 1.4rem;
        box-shadow: 0 2px 6px rgba(247, 137, 59, 0.08);
    }

    /* Dynamic Card Lift & Pulse Animations */
    .card-urgent {
        background: #FFFFFF;
        border-radius: 12px;
        border: 1px solid #FCDEDE;
        border-left: 5px solid #B82C35 !important;
        padding: 12px 16px;
        margin-bottom: 10px;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        animation: pulse-urgent 3.2s infinite ease-in-out;
    }
    .card-urgent:hover {
        transform: translateY(-2.5px);
        box-shadow: 0 8px 20px rgba(184, 44, 53, 0.16);
    }
    @keyframes pulse-urgent {
        0% {
            box-shadow: 0 1px 3px rgba(184, 44, 53, 0.08);
            border-left-color: #B82C35;
        }
        50% {
            box-shadow: 0 5px 18px rgba(184, 44, 53, 0.24);
            border-left-color: #e0333e;
        }
        100% {
            box-shadow: 0 1px 3px rgba(184, 44, 53, 0.08);
            border-left-color: #B82C35;
        }
    }

    .card-soon {
        background: #FFFFFF;
        border-radius: 12px;
        border: 1px solid #FEEDDC;
        border-left: 5px solid #F7893B !important;
        padding: 12px 16px;
        margin-bottom: 10px;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .card-soon:hover {
        transform: translateY(-2.5px);
        box-shadow: 0 8px 20px rgba(247, 137, 59, 0.15);
    }

    .card-safe {
        background: #FFFFFF;
        border-radius: 12px;
        border: 1px solid #E5EFE1;
        border-left: 5px solid #749563 !important;
        padding: 12px 16px;
        margin-bottom: 10px;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .card-safe:hover {
        transform: translateY(-2.5px);
        box-shadow: 0 8px 20px rgba(116, 149, 99, 0.15);
    }

    /* Fast AI Scan Hero Card with Gradient & Glow */
    .ai-hero-card {
        background: linear-gradient(135deg, #FFFDF4 0%, #F5FBF1 50%, #FFF9E6 100%);
        border: 1px solid #D8E4D0;
        border-radius: 14px;
        padding: 14px 18px;
        margin-bottom: 18px;
        box-shadow: 0 3px 10px rgba(116, 149, 99, 0.08);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .ai-hero-card:hover {
        box-shadow: 0 6px 18px rgba(116, 149, 99, 0.14);
    }

    /* Organic Floating Animations */
    @keyframes float-brand {
        0% { transform: translateY(0px) rotate(0deg); }
        50% { transform: translateY(-4px) rotate(4deg); }
        100% { transform: translateY(0px) rotate(0deg); }
    }
    .brand-icon {
        display: inline-block;
        animation: float-brand 4s ease-in-out infinite;
    }

    /* Shimmering Badge for AI features */
    @keyframes ai-glow-pulse {
        0% { box-shadow: 0 0 0 0 rgba(116, 149, 99, 0.4); }
        70% { box-shadow: 0 0 0 8px rgba(116, 149, 99, 0); }
        100% { box-shadow: 0 0 0 0 rgba(116, 149, 99, 0); }
    }
    .ai-pulse-pill {
        display: inline-block;
        border-radius: 9999px;
        animation: ai-glow-pulse 2.5s infinite;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_safety_notice() -> None:
    """Renders mandatory food-safety guidance note."""
    st.markdown(
        """
        <div class="safety-notice">
            <strong>⚠️ Safety & Honesty Notice:</strong>
            GrocoPilot is a reminder tool, not a food-safety checker. Dates are estimates unless marked
            <strong>Verified</strong>. Always check the pack and use your senses.
            Do not eat anything that looks, smells, or tastes off.
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.dialog("✨ Quick AI Pack & Expiry Scanner")
def quick_pack_scan_dialog() -> None:
    """
    Instant AI Vision modal to snap ANY grocery pack or bill directly from the dashboard.
    Extracts item name, category, quantity, and exact printed expiry date in 2 seconds.
    """
    st.caption("Point your camera at a grocery package, label, or receipt to automatically detect details and expiry date.")
    st.info("🔒 **Privacy Notice:** Photos are processed in memory by Gemini Vision and discarded immediately.")

    scan_type = st.radio("What would you like to scan?", ["📦 Single Grocery Pack & Expiry Date", "🧾 Supermarket Bill / Receipt"], horizontal=True, key="dlg_quick_scan_type")

    source_mode = st.radio("Choose photo source:", ["Camera", "Upload File"], horizontal=True, key="dlg_quick_source")
    if source_mode == "Camera":
        photo_file = st.camera_input("Point camera at item pack or receipt:", key="dlg_quick_cam")
    else:
        photo_file = st.file_uploader("Upload grocery image:", type=["jpg", "jpeg", "png", "webp"], key="dlg_quick_file")

    if photo_file is not None:
        st.divider()
        col_img, col_info = st.columns([1, 1.2])
        with col_img:
            st.image(photo_file, caption="Held in memory only", width=220)

        with col_info:
            if scan_type.startswith("📦"):
                if st.button("🚀 Detect Pack & Expiry Date", type="primary", use_container_width=True, key="dlg_run_pack_scan"):
                    with st.spinner("🤖 Gemini Flash Vision is reading package details and printed expiry date..."):
                        res = scanner.scan_grocery_pack_and_expiry(photo_file)
                        st.session_state["dlg_pack_res"] = res

                pack_res = st.session_state.get("dlg_pack_res")
                if pack_res:
                    if pack_res["status"] == "ok":
                        item = pack_res["item"]
                        st.success(f"**{item['name']}**")
                        st.write(f"Category: **{item['category']}** • Storage: **{item['storage'].capitalize()}**")
                        if pack_res.get("has_printed_expiry"):
                            st.markdown(f"🏷️ **Exact Expiry Date:** `{item['expiry_date']}` <span class='badge-verified'>Verified</span>", unsafe_allow_html=True)
                            if pack_res.get("raw_date_text"):
                                st.caption(f"Printed on pack: *\"{pack_res['raw_date_text']}\"*")
                        else:
                            st.markdown(f"⏱️ **Estimated Expiry:** `{item['expiry_date']}` <span class='badge-estimated'>Estimated</span>", unsafe_allow_html=True)
                            st.caption("No printed date was visible; applied conservative shelf life.")

                        col_save, col_stage = st.columns(2)
                        with col_save:
                            if st.button("💾 Save to Fridge Now", type="primary", use_container_width=True, key="dlg_save_direct"):
                                db.add_item(item)
                                if "dlg_pack_res" in st.session_state:
                                    del st.session_state["dlg_pack_res"]
                                st.toast(f"Saved '{item['name']}' to kitchen pantry! 🎉")
                                st.rerun()
                        with col_stage:
                            if st.button("➕ Add to Review List", use_container_width=True, key="dlg_stage_direct"):
                                if "staged_items" not in st.session_state:
                                    st.session_state.staged_items = []
                                st.session_state.staged_items.append(item)
                                if "dlg_pack_res" in st.session_state:
                                    del st.session_state["dlg_pack_res"]
                                st.toast(f"Added '{item['name']}' to staging review table!")
                                st.rerun()
                    else:
                        st.error(pack_res.get("error", "Could not read pack."))
            else:
                # Receipt scan
                if st.button("🚀 Extract Items from Bill", type="primary", use_container_width=True, key="dlg_run_bill_scan"):
                    with st.spinner("🤖 Gemini Flash Vision is reading receipt lines and prices..."):
                        b_res = scanner.scan_receipt(photo_file)
                        if b_res["status"] == "ok":
                            items_found = b_res.get("items", [])
                            if not items_found:
                                st.warning("No food items could be identified on this receipt.")
                            else:
                                if "staged_items" not in st.session_state:
                                    st.session_state.staged_items = []
                                st.session_state.staged_items.extend(items_found)
                                st.toast(f"Extracted {len(items_found)} items from receipt into review staging!")
                                st.rerun()
                        else:
                            st.error(b_res.get("error", "Receipt scanning failed."))


def render_dashboard() -> None:
    """Renders the main 'Use First' dashboard screen."""
    logo_b64 = get_logo_base64()
    if logo_b64:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 0.2rem;">
                <img src="data:image/png;base64,{logo_b64}" class="brand-icon" style="width: 52px; height: 52px; border-radius: 14px; box-shadow: 0 4px 14px rgba(116, 149, 99, 0.28); object-fit: contain; background: #2D5A27;" />
                <h1 style="margin: 0; font-size: 2.2rem; display: inline-block;">GrocoPilot</h1>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<h1><span class='brand-icon'>🥬</span> GrocoPilot</h1>", unsafe_allow_html=True)
    st.caption("Never let groceries go to waste. Eat fresh, use what spoils first.")

    render_safety_notice()

    # Fast AI Action Banner with direct Launch button
    with st.container():
        hero_c1, hero_c2 = st.columns([3, 1.3])
        with hero_c1:
            st.markdown(
                """
                <div class="ai-hero-card">
                    <div style="display: flex; align-items: center; gap: 14px;">
                        <span style="font-size: 2rem;" class="brand-icon">✨</span>
                        <div>
                            <strong style="color: #4A6539; font-size: 1.05rem;">Quick AI Pack & Expiry Scanner</strong><br>
                            <span style="color: #555E4E; font-size: 0.85rem;">Snap any grocery pack label or supermarket bill to auto-detect items and exact expiry dates.</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with hero_c2:
            st.write("")
            if st.button("📸 Instant AI Scan", type="primary", use_container_width=True, help="Quickly scan a package label or receipt"):
                quick_pack_scan_dialog()

    # Fetch active items from SQLite
    active_items = db.get_active_items()

    if not active_items:
        st.info("Your pantry is currently empty! Add items or load sample groceries below.")
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🚀 Load 8 Demo Items", use_container_width=True, type="primary"):
                count = db.load_demo_data()
                st.success(f"Loaded {count} demo items! Refreshing...")
                st.rerun()
        return

    # Categorize items into urgency bands
    today = date.today()
    red_items: List[Dict[str, Any]] = []
    yellow_items: List[Dict[str, Any]] = []
    green_items: List[Dict[str, Any]] = []

    for item in active_items:
        band_info = logic.get_urgency_band(item["expiry_date"], as_of_date=today)
        item_with_meta = {**item, "urgency": band_info}
        if band_info["band"] == "RED":
            red_items.append(item_with_meta)
        elif band_info["band"] == "YELLOW":
            yellow_items.append(item_with_meta)
        else:
            green_items.append(item_with_meta)

    # Sort each group by days left ascending
    red_items.sort(key=lambda x: x["urgency"]["days_left"])
    yellow_items.sort(key=lambda x: x["urgency"]["days_left"])
    green_items.sort(key=lambda x: x["urgency"]["days_left"])

    # Header summary metric cards
    attention_count = len(red_items)
    soon_count = len(yellow_items)
    safe_count = len(green_items)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric(label="🚨 Urgent (≤ 2d / Expired)", value=attention_count)
    with col_m2:
        st.metric(label="⚠️ Use Soon (3–5d)", value=soon_count)
    with col_m3:
        st.metric(label="✅ Safe (> 5d)", value=safe_count)
    with col_m4:
        st.metric(label="📦 Total In Kitchen", value=len(active_items))

    # Summary callout
    if attention_count > 0:
        st.warning(f"🔔 **{attention_count} item{'s' if attention_count > 1 else ''} need attention today!** Check or cook these first.")
    else:
        st.success("🎉 Great job! No items urgently expiring today.")

    st.divider()

    # Render groups
    if red_items:
        st.subheader("🚨 Urgent Attention (Expired or ≤ 2 Days Left)")
        for item in red_items:
            render_item_row(item, card_class="card-urgent")

    if yellow_items:
        st.subheader("⚠️ Use Soon (3 to 5 Days Left)")
        for item in yellow_items:
            render_item_row(item, card_class="card-soon")

    if green_items:
        st.subheader("✅ Safe For Now (> 5 Days Left)")
        for item in green_items:
            render_item_row(item, card_class="card-safe")


@st.dialog("📷 Scan Pack Label to Verify Date")
def scan_label_dialog(item: Dict[str, Any]) -> None:
    """
    One-tap modal flow to upgrade an item's date by scanning the printed label.
    Extracts date via Gemini Flash Vision, shows image preview side-by-side
    with detected date, and provides 'Looks right' and 'Edit' buttons.
    Falls back gracefully to manual date entry if scanning fails.
    """
    item_id = item["id"]
    st.markdown(f"### {item['name']}")
    st.caption(f"Current Expiry: **{item['expiry_date']}** ({item['date_source'].capitalize()})")

    # Mandatory privacy notice
    st.info("🔒 **Privacy Notice:** Photos are sent to an AI service for reading and are not stored by this app. Avoid including personal details in the frame.")

    dialog_tabs = st.tabs(["📸 Camera / Image Scan", "✏️ Type Exact Date"])

    with dialog_tabs[0]:
        scan_mode = st.radio("Choose photo input method:", ["Camera", "Upload File"], horizontal=True, key=f"dlg_mode_{item_id}")

        photo_input = None
        if scan_mode == "Camera":
            photo_input = st.camera_input("Point camera at back/side expiry label:", key=f"dlg_cam_{item_id}")
        else:
            photo_input = st.file_uploader("Upload photo of expiry label:", type=["jpg", "jpeg", "png", "webp"], key=f"dlg_file_{item_id}")

        if photo_input is not None:
            st.divider()
            c_img, c_res = st.columns([1, 1.2])

            with c_img:
                st.image(photo_input, caption="Label Photo (Memory only)", width=240)

            with c_res:
                scan_key = f"label_result_{item_id}"
                if st.button("🔍 Read Date with Gemini AI", type="primary", key=f"btn_scan_{item_id}", use_container_width=True):
                    with st.spinner("Reading printed expiry and manufacturing date..."):
                        res = scanner.scan_label(photo_input)
                        st.session_state[scan_key] = res

                # Display result if available
                res = st.session_state.get(scan_key)
                if res:
                    if res["status"] == "ok":
                        det_date = res["detected_date"]
                        st.success(f"**Detected Expiry:** {det_date}")
                        if res.get("raw_date_text"):
                            st.caption(f"Label text: *\"{res['raw_date_text']}\"*")

                        btn_looks, btn_edit = st.columns(2)
                        with btn_looks:
                            if st.button("✅ Looks Right", key=f"looks_right_{item_id}", type="primary", use_container_width=True):
                                db.update_item_expiry(item_id, det_date, date_source="scanned")
                                if scan_key in st.session_state:
                                    del st.session_state[scan_key]
                                st.toast(f"Updated '{item['name']}' expiry to {det_date} (Verified)!", icon="🏷️")
                                st.rerun()

                        with btn_edit:
                            if st.button("✏️ Edit Date", key=f"edit_detected_{item_id}", use_container_width=True):
                                st.session_state[f"show_edit_{item_id}"] = True

                        if st.session_state.get(f"show_edit_{item_id}"):
                            edited_date = st.date_input("Adjust date:", value=date.fromisoformat(det_date), key=f"adj_date_{item_id}")
                            if st.button("Save Adjusted Date", key=f"save_adj_{item_id}", type="primary"):
                                db.update_item_expiry(item_id, edited_date.isoformat(), date_source="scanned")
                                if scan_key in st.session_state:
                                    del st.session_state[scan_key]
                                st.success("Saved verified date!")
                                st.rerun()

                    elif res["status"] in ("no_date", "implausible", "failed"):
                        st.error(res.get("error", "Could not detect date."))
                        st.info("💡 **Manual fallback:** You can enter the date manually below.")
                        fallback_date = st.date_input("Exact Expiry Date:", value=date.today(), key=f"fb_date_{item_id}")
                        if st.button("Save Manual Date", key=f"btn_save_fb_{item_id}", type="primary"):
                            db.update_item_expiry(item_id, fallback_date.isoformat(), date_source="typed")
                            if scan_key in st.session_state:
                                del st.session_state[scan_key]
                            st.success("Date saved as Verified!")
                            st.rerun()

    with dialog_tabs[1]:
        st.markdown("Enter the exact printed date from the package without scanning:")
        manual_date = st.date_input(
            "Expiry Date:",
            value=date.fromisoformat(item["expiry_date"]),
            key=f"manual_tab_date_{item_id}",
        )
        if st.button("Save Verified Date", key=f"save_manual_tab_{item_id}", type="primary"):
            valid, err = logic.validate_date_string(manual_date.isoformat())
            if not valid:
                st.error(err)
            else:
                db.update_item_expiry(item_id, manual_date.isoformat(), date_source="typed")
                st.toast(f"Updated '{item['name']}' to {manual_date.isoformat()} (Verified)!")
                st.rerun()


def render_item_row(item: Dict[str, Any], card_class: str = "card-safe") -> None:
    """Renders a single grocery item row with wholesome palette styling and action buttons."""
    item_id = item["id"]
    urgency = item["urgency"]
    storage_emoji = {"fridge": "❄️ Fridge", "room": "🧺 Room", "freezer": "🧊 Freezer"}.get(item["storage"], "📦 Other")

    # Verification pill
    is_verified = item["date_source"] in ("scanned", "typed")
    badge_html = '<span class="badge-verified">🏷️ Verified</span>' if is_verified else '<span class="badge-estimated">⏱️ Estimated</span>'

    # Opened pill
    opened_html = '<span class="badge-opened">🔓 Opened</span>' if item.get("opened") else ""

    with st.container():
        # Styled card container
        st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
        cols = st.columns([4, 1.1, 1.1, 1.1, 1.5])

        with cols[0]:
            st.markdown(
                f"""
                <strong style="font-size: 1.05rem; color: #1F2937;">{item['name']}</strong> &nbsp; {badge_html} {opened_html}<br>
                <small style="color: #6B7280; font-weight: 500;">
                    {item['category']} • {item['quantity']} {item['unit']} • {storage_emoji}
                    • Exp: <strong style="color: #374151;">{item['expiry_date']}</strong> ({urgency['badge']})
                </small>
                """,
                unsafe_allow_html=True,
            )

        with cols[1]:
            # Mark Used button
            if st.button("✅ Used", key=f"used_{item_id}", help="Mark as eaten/finished", use_container_width=True):
                db.update_item_status(item_id, "used")
                st.toast(f"Marked '{item['name']}' as used! Saved food! 🎉")
                st.rerun()

        with cols[2]:
            # Mark Thrown button
            if st.button("🗑️ Thrown", key=f"thrown_{item_id}", help="Discarded due to spoilage", use_container_width=True):
                db.update_item_status(item_id, "thrown")
                st.toast(f"Marked '{item['name']}' as discarded.", icon="🗑️")
                st.rerun()

        with cols[3]:
            # Opened pack clock button
            if item.get("opened"):
                st.button("🔓 Opened", key=f"open_{item_id}", disabled=True, use_container_width=True)
            else:
                if st.button("📦 Open", key=f"open_{item_id}", help="Start opened-pack clock", use_container_width=True):
                    today_str = date.today().isoformat()
                    new_exp = logic.calculate_opened_expiry(
                        current_expiry_str=item["expiry_date"],
                        opened_date_str=today_str,
                        food_name=item["name"],
                    )
                    db.mark_item_opened(item_id, new_exp)
                    st.toast(f"Opened clock started! New expiry: {new_exp}", icon="⏱️")
                    st.rerun()

        with cols[4]:
            # One-tap AI Vision Scan Label flow
            if st.button("✨ AI Scan", key=f"scan_btn_{item_id}", help="Use Gemini Flash AI to read printed expiry date from pack", use_container_width=True):
                scan_label_dialog(item)

        st.markdown('</div>', unsafe_allow_html=True)


def render_add_items() -> None:
    """
    Renders the Add Items screen with 3 tabs:
      (a) ✨ Quick AI Vision Scanner (Single Grocery Pack & Expiry OR Receipt)
      (b) 📝 Paste Order Text (Blinkit, Zepto, Instamart, SMS)
      (c) ⚡ Manual Quick Add with autocomplete
    Followed by the interactive Review Screen (st.data_editor).
    """
    st.title("➕ Add Groceries to Fridge")

    if "staged_items" not in st.session_state:
        st.session_state.staged_items = []

    # If there are items waiting in staging review, display them prominently at the top
    if st.session_state.staged_items:
        render_review_screen()
        st.divider()

    tabs = st.tabs([
        "✨ Quick AI Vision Scanner",
        "📝 Paste Order Text",
        "⚡ Manual Quick Add",
    ])

    # ------------------ TAB 1: QUICK AI VISION SCANNER ------------------
    with tabs[0]:
        st.subheader("🤖 Quick AI Vision Scanner")
        st.caption("Point your camera or upload a photo. Gemini Flash Vision reads grocery details and exact printed expiry dates in seconds.")

        # Mandatory Privacy notice
        st.info("🔒 **Privacy Notice:** Photos are sent in-memory to Google Gemini AI for reading and are not stored by this app. Avoid including personal details in the frame.")

        # Session API call monitor
        api_count = scanner.get_api_call_count()
        if api_count > 0:
            st.caption(f"⚡ Gemini API calls used this session: **{api_count}**")
        if api_count >= scanner.API_CALL_WARNING_THRESHOLD:
            st.warning(f"⚠️ High API usage alert ({api_count} calls). The Gemini free tier has rate limits, so consider spacing out requests.")

        ai_scan_choice = st.radio(
            "Select scan target:",
            ["📦 Single Grocery Pack & Expiry Date (1-Shot AI Reader)", "🧾 Supermarket Bill / Order Screenshot (Multi-Item)"],
            horizontal=True,
            key="tab_ai_scan_choice",
        )

        if ai_scan_choice.startswith("📦"):
            # Single Pack & Expiry Date Scanner
            st.markdown("#### 📦 Scan Any Grocery Pack (Reads Item & Expiry Date)")
            st.caption("Take a photo of any milk carton, bread pack, curd tub, spice jar, or produce.")

            pack_col1, pack_col2 = st.columns(2)
            with pack_col1:
                pack_source = st.radio("Photo Input:", ["Camera", "Upload File"], horizontal=True, key="pack_input_mode")
            with pack_col2:
                pack_pdate = st.date_input("Purchase Date:", value=date.today(), key="single_pack_pdate")

            pack_img = None
            if pack_source == "Camera":
                pack_img = st.camera_input("Point camera at grocery package or printed date:", key="pack_cam_input")
            else:
                pack_img = st.file_uploader("Upload pack photo:", type=["jpg", "jpeg", "png", "webp", "heic"], key="pack_file_input")

            if pack_img is not None:
                p_col_left, p_col_right = st.columns([1, 1.2])
                with p_col_left:
                    st.image(pack_img, caption="Pack Preview (Memory only)", width=260)

                with p_col_right:
                    if st.button("🚀 Scan Item & Expiry with Gemini AI", type="primary", use_container_width=True, key="btn_scan_pack_ai"):
                        with st.spinner("🤖 Gemini Flash Vision is reading item details & printed expiry date..."):
                            res = scanner.scan_grocery_pack_and_expiry(pack_img, purchase_date_str=pack_pdate.isoformat())
                            st.session_state["tab_pack_scan_result"] = res

                    pack_res = st.session_state.get("tab_pack_scan_result")
                    if pack_res:
                        if pack_res["status"] == "ok":
                            item = pack_res["item"]
                            st.success(f"**{item['name']}**")
                            st.write(f"Category: **{item['category']}** • Quantity: **{item['quantity']} {item['unit']}** • Storage: **{item['storage'].capitalize()}**")

                            if pack_res.get("has_printed_expiry"):
                                st.markdown(f"🏷️ **Exact Expiry Date:** `{item['expiry_date']}` &nbsp; <span class='badge-verified'>🏷️ Verified</span>", unsafe_allow_html=True)
                                if pack_res.get("raw_date_text"):
                                    st.caption(f"Printed on label: *\"{pack_res['raw_date_text']}\"*")
                            else:
                                st.markdown(f"⏱️ **Estimated Expiry:** `{item['expiry_date']}` &nbsp; <span class='badge-estimated'>⏱️ Estimated</span>", unsafe_allow_html=True)
                                st.caption("No printed date was visible on this face; applied conservative shelf life.")

                            col_act1, col_act2 = st.columns(2)
                            with col_act1:
                                if st.button("💾 Save Directly to Fridge", type="primary", use_container_width=True, key="btn_save_pack_fridge"):
                                    db.add_item(item)
                                    if "tab_pack_scan_result" in st.session_state:
                                        del st.session_state["tab_pack_scan_result"]
                                    st.toast(f"Saved '{item['name']}' to fridge! 🎉")
                                    st.rerun()

                            with col_act2:
                                if st.button("➕ Add to Review List", use_container_width=True, key="btn_stage_pack"):
                                    st.session_state.staged_items.append(item)
                                    if "tab_pack_scan_result" in st.session_state:
                                        del st.session_state["tab_pack_scan_result"]
                                    st.toast(f"Added '{item['name']}' to staging review table!")
                                    st.rerun()
                        else:
                            st.error(pack_res.get("error", "Could not scan item."))

        else:
            # Multi-Item Receipt Scanner
            st.markdown("#### 🧾 Scan Supermarket Bill or App Screenshot")
            st.caption("Upload or photograph a grocery receipt (Blinkit, Zepto, DMart, etc.). Gemini extracts all items, prices, and quantities.")

            upload_col1, upload_col2 = st.columns([1, 1])
            with upload_col1:
                uploaded_file = st.file_uploader(
                    "Choose a receipt image:",
                    type=["jpg", "jpeg", "png", "webp", "heic"],
                    key="receipt_uploader",
                )
            with upload_col2:
                camera_receipt = st.camera_input("Or take a photo of the receipt:", key="receipt_camera")

            receipt_input = uploaded_file or camera_receipt

            if receipt_input is not None:
                r_col_img, r_col_act = st.columns([1, 1.2])
                with r_col_img:
                    st.image(receipt_input, caption="Receipt Preview (Held in memory only)", width=280)

                with r_col_act:
                    st.markdown("### Process Receipt")
                    receipt_pdate = st.date_input("Purchase Date on receipt:", value=date.today(), key="receipt_pdate")

                    if st.button("🚀 Scan Receipt with Gemini Flash Vision", type="primary", use_container_width=True):
                        with st.spinner("🤖 Gemini Flash Vision is reading grocery lines, prices, and quantities..."):
                            scan_res = scanner.scan_receipt(receipt_input, default_purchase_date=receipt_pdate.isoformat())

                        if scan_res["status"] == "ok":
                            items_found = scan_res.get("items", [])
                            if not items_found:
                                st.warning("No food items could be identified on this receipt. Try pasting text or manual quick adding.")
                            else:
                                st.session_state.staged_items.extend(items_found)
                                st.success(f"🎉 Successfully extracted {len(items_found)} grocery items! Review them in the staging table above.")
                                st.rerun()
                        else:
                            st.error(f"❌ Scanning failed: {scan_res.get('error')}")
                            st.info("💡 **Manual Fallback:** You can instantly add items using the **📝 Paste Order Text** tab or **⚡ Manual Quick Add** tab.")

    # ------------------ TAB 2: PASTE ORDER TEXT ------------------
    with tabs[1]:
        st.subheader("Paste Order Text or SMS Bill")
        st.caption("Paste grocery order summaries from Blinkit, Zepto, Swiggy Instamart, BigBasket, or SMS receipts.")

        sample_text = (
            "Amul Taaza Toned Milk 1 L x 2 - Rs 108\n"
            "Country Tomatoes 1 kg - Rs 40\n"
            "Fresh Coriander Leaves 1 bunch - Rs 15\n"
            "Harvest Gold Brown Bread 400g - Rs 50\n"
            "Amul Salted Butter 100g - Rs 58\n"
            "Subtotal: Rs 271\n"
            "Delivery Fee: Rs 29\n"
            "Total Amount Paid: Rs 300"
        )

        col_sample, col_clear = st.columns([2, 1])
        with col_sample:
            if st.button("📋 Load Sample Blinkit / Zepto Bill", help="Insert sample text to test parsing"):
                st.session_state["pasted_bill_input"] = sample_text

        bill_text = st.text_area(
            "Order text:",
            value=st.session_state.get("pasted_bill_input", ""),
            height=160,
            placeholder="e.g.\nAmul Toned Milk 1 L - Rs 54\nFresh Spinach 1 bunch - Rs 25\nTotal: Rs 79",
            key="pasted_bill_area",
        )

        p_col1, p_col2 = st.columns(2)
        with p_col1:
            p_date = st.date_input("Purchase Date for this bill:", value=date.today(), key="paste_p_date")

        with p_col2:
            st.write("")
            st.write("")
            if st.button("🔍 Parse & Review Items", type="primary", use_container_width=True):
                if not bill_text.strip():
                    st.warning("Please paste some order text first.")
                else:
                    parsed = logic.parse_pasted_order_text(bill_text, default_purchase_date=p_date.isoformat())
                    if not parsed:
                        st.error("No grocery items could be identified from the text. Check formatting.")
                    else:
                        st.session_state.staged_items.extend(parsed)
                        st.success(f"Parsed {len(parsed)} food items! (Non-food totals & fees were excluded).")
                        st.rerun()

    # ------------------ TAB 3: MANUAL QUICK ADD ------------------
    with tabs[2]:
        st.subheader("Manual Quick Add with Autocomplete")
        st.caption("Quickly add an item with smart autocomplete from our 35+ Indian household food shelf-life database.")

        with st.expander("📷 Have a photo of a loose vegetable or item without a label? Identify it with AI"):
            st.caption("Snap a photo of loose produce or a single grocery pack. Gemini Flash Vision will identify the food and category.")
            front_photo = st.file_uploader("Upload product/vegetable photo:", type=["jpg", "jpeg", "png", "webp"], key="front_photo_uploader")
            if front_photo is not None:
                st.image(front_photo, width=250)
                if st.button("🤖 Identify Food From Photo", key="btn_identify_front"):
                    with st.spinner("Analyzing image..."):
                        ident_res = scanner.identify_front(front_photo)
                    if ident_res["status"] == "ok":
                        st.session_state["qa_custom_name"] = ident_res["name"]
                        st.success(f"Detected: **{ident_res['name']}** ({ident_res['category']})!")
                        st.rerun()
                    else:
                        st.error(ident_res.get("error", "Could not identify item."))

        food_names = logic.get_all_food_names()
        categories = logic.get_all_categories()

        qa_col1, qa_col2 = st.columns(2)
        with qa_col1:
            selected_food = st.selectbox(
                "Food item name (Type to search):",
                options=[""] + food_names,
                index=0,
                key="qa_food_select",
            )
            # Custom name if not in list
            custom_name = st.text_input("Or type custom name if not listed:", value="", key="qa_custom_name")
            final_name = custom_name.strip() if custom_name.strip() else selected_food

        # Auto-match category and default storage
        matched_category = "General"
        shelf_days = 7
        if final_name:
            days, cat, is_known = logic.get_shelf_life_days(final_name, storage="fridge")
            matched_category = cat
            shelf_days = days

        with qa_col2:
            cat_idx = categories.index(matched_category) if matched_category in categories else 0
            chosen_cat = st.selectbox("Category:", options=categories, index=cat_idx, key="qa_cat_select")

        qa_col3, qa_col4, qa_col5 = st.columns(3)
        with qa_col3:
            qa_qty = st.number_input("Quantity:", min_value=0.1, value=1.0, step=0.5, key="qa_qty")
        with qa_col4:
            qa_unit = st.selectbox("Unit:", options=["pack", "kg", "g", "L", "ml", "pcs", "bunch", "box"], index=0, key="qa_unit")
        with qa_col5:
            qa_price = st.number_input("Price (₹, optional):", min_value=0.0, value=0.0, step=10.0, key="qa_price")

        qa_col6, qa_col7, qa_col8 = st.columns(3)
        with qa_col6:
            default_storage = db.get_setting(f"storage_default_{chosen_cat}", default="fridge" if chosen_cat in ("Dairy", "Produce", "Meat") else "room")
            qa_storage = st.selectbox("Storage place:", options=["fridge", "room", "freezer"], index=["fridge", "room", "freezer"].index(default_storage), key="qa_storage")
        with qa_col7:
            qa_pdate = st.date_input("Purchase Date:", value=date.today(), key="qa_pdate")
        with qa_col8:
            # Calculated estimated expiry preview
            exp_iso, _, _ = logic.calculate_estimated_expiry(final_name or "food", qa_pdate.isoformat(), qa_storage)
            qa_expdate = st.date_input("Expiry Date (auto-calculated):", value=date.fromisoformat(exp_iso), key="qa_expdate")

        # Remember custom override option
        remember_override = st.checkbox(
            f"Remember this shelf life for '{final_name}' for future additions",
            value=False,
            disabled=not bool(final_name),
            key="qa_remember",
        )

        if st.button("➕ Add to Staging Review", type="primary", disabled=not bool(final_name)):
            if remember_override and final_name:
                diff_days = (qa_expdate - qa_pdate).days
                if diff_days > 0:
                    db.save_user_override(final_name, chosen_cat, qa_storage, diff_days)
                    st.toast(f"Saved custom rule: {final_name} -> {diff_days} days in {qa_storage}!")

            new_staged = {
                "name": final_name.title(),
                "category": chosen_cat,
                "quantity": float(qa_qty),
                "unit": qa_unit,
                "price": float(qa_price) if qa_price > 0 else None,
                "storage": qa_storage,
                "purchase_date": qa_pdate.isoformat(),
                "expiry_date": qa_expdate.isoformat(),
                "date_source": "estimated",
                "is_matched": True,
            }
            st.session_state.staged_items.append(new_staged)
            st.success(f"Added '{final_name}' to review staging table!")
            st.rerun()


def render_review_screen() -> None:
    """
    Renders the editable staging table (st.data_editor).
    NOTHING is saved until the user presses 'Save to my fridge'.
    """
    import pandas as pd

    st.subheader("📋 Review Detected Items Before Saving")
    st.caption("Edit quantities, fix dates, or delete wrong rows. **Nothing is saved to your database until you click 'Save to my fridge' below.**")

    # Flag if any unmatched items exist
    unmatched = [it["name"] for it in st.session_state.staged_items if not it.get("is_matched", True)]
    if unmatched:
        st.warning(f"⚠️ Unrecognized items: **{', '.join(unmatched)}**. Default shelf-life was applied; please verify their expiry dates.")

    df = pd.DataFrame(st.session_state.staged_items)

    # Configure editable columns
    column_config = {
        "name": st.column_config.TextColumn("Item Name", required=True),
        "category": st.column_config.SelectboxColumn("Category", options=logic.get_all_categories(), required=True),
        "quantity": st.column_config.NumberColumn("Qty", min_value=0.1, step=0.5, required=True),
        "unit": st.column_config.TextColumn("Unit", required=True),
        "price": st.column_config.NumberColumn("Price (₹)", min_value=0.0, format="₹%.2f"),
        "storage": st.column_config.SelectboxColumn("Storage", options=["fridge", "room", "freezer"], required=True),
        "purchase_date": st.column_config.TextColumn("Purchased (YYYY-MM-DD)", required=True),
        "expiry_date": st.column_config.TextColumn("Expiry (YYYY-MM-DD)", required=True),
        "date_source": st.column_config.TextColumn("Source", disabled=True),
        "is_matched": None,  # Hide from table display
    }

    # Interactive data editor
    edited_df = st.data_editor(
        df,
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True,
        key="staging_data_editor",
    )

    btn_col1, btn_col2 = st.columns([2, 1])
    with btn_col1:
        if st.button("💾 Save to My Fridge", type="primary", use_container_width=True):
            records = edited_df.to_dict(orient="records")
            if not records:
                st.warning("No items to save.")
                return

            # Validate dates
            errors = []
            for idx, r in enumerate(records, 1):
                p_valid, p_err = logic.validate_date_string(str(r.get("purchase_date", "")))
                if not p_valid:
                    errors.append(f"Row {idx} ('{r.get('name')}'): {p_err}")
                e_valid, e_err = logic.validate_date_string(str(r.get("expiry_date", "")))
                if not e_valid:
                    errors.append(f"Row {idx} ('{r.get('name')}'): {e_err}")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                saved_count = db.add_items_bulk(records)
                st.session_state.staged_items = []
                st.success(f"🎉 Successfully saved {saved_count} items to your fridge!")
                st.rerun()

    with btn_col2:
        if st.button("🧹 Discard All Staged", use_container_width=True):
            st.session_state.staged_items = []
            st.toast("Discarded staging list.")
            st.rerun()


def render_inventory() -> None:
    """Renders the Inventory screen with search and filter by storage location."""
    st.title("📋 Kitchen Inventory")
    st.caption("All currently active grocery items in your fridge, room pantry, and freezer.")

    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        search_query = st.text_input("🔍 Search by name or category:", placeholder="e.g. milk, paneer, produce...")
    with col_s2:
        storage_filter = st.selectbox("Storage place:", options=["All", "Fridge", "Room", "Freezer"])

    items = db.get_active_items(
        storage_filter=storage_filter.lower() if storage_filter != "All" else None,
        search_query=search_query,
    )

    st.write(f"Showing **{len(items)}** active items:")

    if not items:
        st.info("No active grocery items found matching your filters.")
        return

    # Render as interactive table or structured cards
    for item in items:
        band_info = logic.get_urgency_band(item["expiry_date"])
        item_with_meta = {**item, "urgency": band_info}
        render_item_row(item_with_meta)


def render_recipes() -> None:
    """
    Renders the Recipe Suggestions screen.
    Prioritizes active items closest to expiring, producing 3 home-style Indian dishes.
    Supports live Gemini Flash AI generation with offline backup from data/recipes.json.
    """
    st.title("🍳 Smart Recipes to Rescue Food")
    st.caption("GrocoPilot analyzes what's about to spoil and suggests 3 practical home-style Indian meals.")

    render_safety_notice()

    cookable = recipes.get_cookable_items()

    if not cookable:
        st.info("No active, unexpired groceries found in your kitchen! Add some items or load sample groceries.")
        if st.button("🚀 Load 8 Demo Items", key="recipe_load_demo", type="primary"):
            db.load_demo_data()
            st.rerun()
        return

    # Highlight ingredients prioritized by days left
    st.subheader("🛒 Ingredients in Your Kitchen (Sorted by Urgency)")
    item_pills = []
    for it in cookable[:8]:
        days = it["days_left"]
        badge_color = "#EF4444" if days <= 2 else ("#F59E0B" if days <= 5 else "#10B981")
        item_pills.append(
            f"<span style='background: {badge_color}22; color: {badge_color}; border: 1px solid {badge_color}55; padding: 3px 10px; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; margin-right: 6px; display: inline-block; margin-bottom: 6px;'>"
            f"{it['name']} ({days}d left)</span>"
        )
    st.markdown("".join(item_pills), unsafe_allow_html=True)

    st.write("")
    btn_c1, btn_c2 = st.columns([1.5, 1.5])
    with btn_c1:
        if st.button("✨ Generate AI Chef Recipes (Gemini Flash)", type="primary", use_container_width=True):
            with st.spinner("🤖 Gemini Flash is designing 3 home-style Indian recipes to rescue your food..."):
                st.session_state["recipe_result"] = recipes.suggest_recipes(cookable)

    with btn_c2:
        if st.button("📖 Show Curated Offline Recipes", use_container_width=True):
            st.session_state["recipe_result"] = {
                "status": "ok",
                "recipes": recipes.get_offline_suggestions(cookable),
                "source": "offline",
            }

    # Display recipes
    res = st.session_state.get("recipe_result")
    if res:
        st.divider()
        if res.get("source") == "offline" or res.get("status") == "fallback":
            st.caption("ℹ️ Showing recipes from our curated offline Indian kitchen database.")
        else:
            st.caption("⚡ Generated by Gemini Flash AI tailored to your exact kitchen inventory.")

        rec_list = res.get("recipes", [])
        if not rec_list:
            st.warning("No matching recipes found.")
            return

        for idx, rec in enumerate(rec_list, 1):
            with st.container():
                st.markdown(
                    f"""
                    <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 12px; padding: 18px; margin-bottom: 18px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <h3 style="margin: 0; color: #111827;">{idx}. {rec['title']}</h3>
                            <span style="background: #E0E7FF; color: #3730A3; font-weight: 600; font-size: 0.8rem; padding: 3px 10px; border-radius: 9999px;">
                                ⏱️ {rec.get('time_minutes', 15)} mins
                            </span>
                        </div>
                        <p style="color: #92400E; background: #FEF3C7; padding: 6px 12px; border-radius: 6px; font-size: 0.85rem; font-weight: 500; margin-bottom: 12px;">
                            🚨 <strong>Why Now:</strong> {rec.get('why_now', 'Helps use up fresh ingredients.')}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    st.markdown("**🥬 Uses from your kitchen:**")
                    uses = rec.get("uses_items", [])
                    st.markdown(", ".join(f"`{u}`" for u in uses) if uses else "Kitchen staples")
                with col_u2:
                    st.markdown("**🧂 Common pantry extras needed:**")
                    extra = rec.get("needs_extra", [])
                    st.markdown(", ".join(f"`{e}`" for e in extra) if extra else "None")

                with st.expander(f"👩‍🍳 View Cooking Steps for {rec['title']}", expanded=True):
                    for step_num, step in enumerate(rec.get("steps", []), 1):
                        st.markdown(f"**{step_num}.** {step}")

                st.write("")


def render_waste_summary() -> None:
    """
    Renders the Waste and Savings summary screen.
    Tracks what was eaten (saved) vs thrown away this month.
    STRICT HONEST ACCOUNTING:
      - Uses only actual known prices for valuations.
      - Never guesses or estimates missing prices.
    """
    st.title("📊 Food Waste & Financial Savings")
    st.caption("Track what you rescued, what spoiled, and real rupees saved this month.")

    # Honest accounting alert banner
    st.info(
        "💡 **Honest Valuation Rule:** Cost figures strictly include items where the exact purchase price "
        "was recorded on the bill or entered by you. Missing prices are never guessed or fabricated."
    )

    current_month_prefix = date.today().strftime("%Y-%m")
    summary = db.get_waste_summary(month_prefix=current_month_prefix)

    used_count = summary["used_count"]
    used_val = summary["used_value"]
    thrown_count = summary["thrown_count"]
    thrown_val = summary["thrown_value"]
    total_processed = used_count + thrown_count

    rescue_rate = (used_count / total_processed * 100.0) if total_processed > 0 else 100.0

    # Metric Cards with Wholesome Color Styling
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric(
            label="🌿 Groceries Rescued (Used)",
            value=f"₹{used_val:.2f}",
            delta=f"{used_count} items eaten",
        )
    with col_m2:
        st.metric(
            label="🗑️ Food Lost to Waste (Thrown)",
            value=f"₹{thrown_val:.2f}",
            delta=f"-{thrown_count} items discarded" if thrown_count > 0 else "0 discarded",
            delta_color="inverse",
        )
    with col_m3:
        st.metric(
            label="🏆 Food Rescue Efficiency",
            value=f"{rescue_rate:.1f}%",
            delta="Food saved ratio",
        )

    # Progress bar with wholesome color styling
    st.progress(rescue_rate / 100.0, text=f"Monthly Rescue Efficiency: {rescue_rate:.1f}% of consumed food saved from the bin")

    st.divider()

    # Detailed history breakdown
    tab_used, tab_thrown = st.tabs([
        f"🎉 Rescued Food History ({used_count})",
        f"🗑️ Discarded Food History ({thrown_count})",
    ])

    with tab_used:
        used_items = summary.get("used_items", [])
        if not used_items:
            st.info("No items marked as used yet this month. When you eat groceries, click '✅ Used' on the dashboard!")
        else:
            import pandas as pd
            df_used = pd.DataFrame(used_items)
            display_cols = ["name", "category", "quantity", "unit", "price", "status_date"]
            df_used = df_used[[c for c in display_cols if c in df_used.columns]]
            df_used.rename(columns={"status_date": "consumed_date", "price": "price (₹)"}, inplace=True)
            st.dataframe(df_used, use_container_width=True)

    with tab_thrown:
        thrown_items = summary.get("thrown_items", [])
        if not thrown_items:
            st.success("🎉 Amazing! Zero food discarded this month. Keep it up!")
        else:
            import pandas as pd
            df_thrown = pd.DataFrame(thrown_items)
            display_cols = ["name", "category", "quantity", "unit", "price", "status_date"]
            df_thrown = df_thrown[[c for c in display_cols if c in df_thrown.columns]]
            df_thrown.rename(columns={"status_date": "discarded_date", "price": "price (₹)"}, inplace=True)
            st.dataframe(df_thrown, use_container_width=True)
            st.caption("Tip: Look at repeat items in this list to adjust how much you buy next trip!")


def render_settings() -> None:
    """Renders the settings screen to manage defaults, sample data, and data reset."""
    import os
    st.title("⚙️ Settings & System Status")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        try:
            api_key = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
        except Exception:
            pass
    api_key_set = bool(api_key)
    if api_key_set:
        st.success("🟢 **Gemini Flash Vision Connected:** Fast receipt and packaging OCR active!")
    else:
        st.warning("⚠️ **GEMINI_API_KEY Not Set:** Running in smart manual fallback mode (order text pasting & autocomplete quick-add fully functional).")
        st.caption("To activate live AI scanning, set the environment variable: `$env:GEMINI_API_KEY='your_key'`")

    api_calls = scanner.get_api_call_count()
    st.write(f"Session AI API calls made: **{api_calls}**")
    if api_calls >= scanner.API_CALL_WARNING_THRESHOLD:
        st.warning("⚠️ High API usage alert! Spacing out scans helps avoid free tier rate limit errors.")

    st.divider()

    st.subheader("🚀 Hackathon Quick Start")
    st.write("Need sample data to present the dashboard to the judges?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📥 Load 8 Demo Items", use_container_width=True, type="primary"):
            count = db.load_demo_data()
            st.success(f"Added {count} realistic demo items across Red, Yellow, and Green bands!")
            st.rerun()

    with col2:
        if st.button("🧹 Clear All Data", use_container_width=True):
            db.clear_all_data()
            st.warning("Cleared all grocery items and overrides.")
            st.rerun()

    st.divider()

    st.subheader("📦 Default Storage per Category")
    st.caption("Choose default storage location when auto-detecting items.")

    categories = logic.get_all_categories()
    for cat in categories:
        current_def = db.get_setting(f"storage_default_{cat}", default="fridge" if cat in ("Dairy", "Produce", "Meat") else "room")
        options = ["fridge", "room", "freezer"]
        idx = options.index(current_def) if current_def in options else 0
        new_val = st.selectbox(
            f"Default for {cat}:",
            options=options,
            index=idx,
            key=f"setting_cat_{cat}",
        )
        if new_val != current_def:
            db.set_setting(f"storage_default_{cat}", new_val)
            st.toast(f"Saved default storage for {cat} -> {new_val}")


# 4. Main Navigation Routing
def main() -> None:
    with st.sidebar:
        logo_path = Path("assets/logo.png")
        if logo_path.exists():
            st.image("assets/logo.png", use_container_width=True)
            st.markdown("<p style='text-align: center; color: #555E4E; font-size: 0.95rem; margin-top: -8px; margin-bottom: 8px;'><em>Eat fresh. Waste less.</em></p>", unsafe_allow_html=True)
        else:
            st.title("🥬 GrocoPilot")
            st.markdown("*Eat fresh. Waste less.*")
        st.divider()
        nav_options = [
            "🏠 Use First (Dashboard)",
            "➕ Add Items",
            "📋 Inventory",
            "🍳 Recipes",
            "📊 Waste & Savings",
            "⚙️ Settings",
        ]

        # Support direct URL navigation via query param ?page=add or ?page=recipes
        param_page = st.query_params.get("page", "")
        default_idx = 0
        if param_page:
            for idx, opt in enumerate(nav_options):
                if param_page.lower() in opt.lower():
                    default_idx = idx
                    break

        page = st.radio(
            "Navigation",
            options=nav_options,
            index=default_idx,
            key="main_nav_radio",
        )

        st.divider()
        st.caption("GrocoPilot v1.0 • Built with Streamlit & SQLite")

    if page == "🏠 Use First (Dashboard)":
        render_dashboard()
    elif page == "➕ Add Items":
        render_add_items()
    elif page == "📋 Inventory":
        render_inventory()
    elif page == "🍳 Recipes":
        render_recipes()
    elif page == "📊 Waste & Savings":
        render_waste_summary()
    elif page == "⚙️ Settings":
        render_settings()


if __name__ == "__main__":
    main()

