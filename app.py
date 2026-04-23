import io
import json
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import pytz
import streamlit as st
from google_play_scraper import Sort, reviews

# 1. Page Config
st.set_page_config(page_title="RW Pro Live Checker", page_icon="🚀", layout="wide")

# 2. UI Styling (Professional Theme)
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem !important; }
    .stDataFrame td { white-space: normal !important; word-wrap: break-word !important; }
    .stButton > button {
        width: 100% !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        background: linear-gradient(135deg, #f8fbff 0%, #edf4ff 100%) !important;
        color: #0f172a !important;
        border: 1px solid #dbe4ff !important;
    }
    .small-counter {
        border: 1px solid #2ecc71;
        background-color: #f0fff4;
        padding: 10px 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        display: inline-block;
        font-size: 18px;
    }
    .small-counter b { color: #16a34a; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- CONSTANTS ---
IST_TZ = pytz.timezone("Asia/Kolkata")
DATA_DIR = "data"
APP_DB_PATH = os.path.join(DATA_DIR, "apps_config.json")

# --------- Helpers ---------
def ensure_db_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(APP_DB_PATH):
        with open(APP_DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_id(url):
    if not url: return None
    clean = url.strip()
    if re.fullmatch(r"[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+", clean): return clean
    match = re.search(r"id=([a-zA-Z0-9._]+)", clean)
    return match.group(1) if match else None

# --------- CORE FETCH LOGIC (UNLIMITED & ACCURATE) ---------
def fetch_logic(aid, target_dt, depth=1000, star_values=None, hint_values=None):
    all_raw = []
    token = None
    stars_set = set(star_values or [])
    matches = []
    
    # Smart Tracking: Combination of User + Review to allow same names with different reviews
    seen_combinations = set()

    # Scan loop
    for _ in range(depth):
        try:
            res, token = reviews(
                aid, lang="en", country="in", 
                sort=Sort.NEWEST, count=100, 
                continuation_token=token
            )
            if not res: break
            
            all_raw.extend(res)
            
            # Check date boundary
            last_review_time = res[-1]["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()
            if last_review_time < target_dt:
                break
            if not token: break
        except:
            break

    for r in all_raw:
        rev_time = r["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ)
        if rev_time.date() != target_dt:
            continue
        
        if stars_set and int(r.get("score", 0)) not in stars_set:
            continue

        text = (r.get("content") or "").strip()
        user = (r.get("userName") or "Unknown").strip()
        
        # Hint Matching Logic
        is_match = False
        if not hint_values:
            is_match = True
        else:
            for hint in hint_values:
                h = hint.lower().strip()
                # User name ya Review ke end mein hint hona chahiye
                if text.lower().endswith(h) or user.lower().endswith(h):
                    is_match = True
                    break
        
        if is_match:
            # UNIQUE KEY: User + Text combination
            # Taaki agar same naam ke 2 log hon par unka comment alag ho, toh wo miss na ho.
            unique_key = f"{user.lower()}|||{text.lower()}"
            
            if unique_key not in seen_combinations:
                matches.append({
                    "User": user,
                    "Review": text,
                    "App ID": aid,
                    "Rating": f"{r.get('score', 0)}/5",
                    "Date": rev_time.strftime("%Y-%m-%d"),
                    "Time": rev_time.strftime("%H:%M:%S"),
                })
                seen_combinations.add(unique_key)
                
    return matches

# --------- PAGES ---------
def render_manual_page():
    st.subheader("🚀 Professional Deep Scanner")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        app_url = st.text_input("Play Store URL / Package ID", "com.ideopay.user")
    with col2:
        target_date = st.date_input("Select Date", datetime.now(IST_TZ).date())

    with st.expander("⚙️ Advanced Filters (Optional)"):
        score_filter = st.selectbox("Star Rating", [None, 5, 4, 3, 2, 1])
        hint_val = st.text_input("End Word / Hint (e.g. # or ..)")

    if st.button("🔍 Run Live Scan"):
        aid = extract_id(app_url)
        if not aid:
            st.error("Invalid URL or Package ID")
            return
            
        with st.spinner(f"Fetching every single review for {aid}..."):
            hints = [hint_val] if hint_val else []
            found = fetch_logic(aid, target_date, depth=2000, # Increased depth for large apps
                                   star_values=[score_filter] if score_filter else [], 
                                   hint_values=hints)
            
            st.session_state.manual_matches = found
            st.success(f"Scan complete! Total entries found: {len(found)}")

    if "manual_matches" in st.session_state and st.session_state.manual_matches:
        df = pd.DataFrame(st.session_state.manual_matches)
        st.markdown(f'<div class="small-counter">Live Count: <b>{len(df)}</b></div>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
        
        # Excel Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Reviews')
        st.download_button("📥 Download Report (Excel)", output.getvalue(), f"Report_{aid}.xlsx")

def render_add_app_page():
    st.subheader("📌 App Monitor List")
    apps = load_json(APP_DB_PATH)
    
    with st.form("add_form", clear_on_submit=True):
        st.write("Add new app to monitor")
        name = st.text_input("Display Name")
        url = st.text_input("App Link")
        hints = st.text_input("Hints (comma separated)")
        submitted = st.form_submit_button("Add to List")
        
        if submitted:
            aid = extract_id(url)
            if not aid or not name:
                st.error("Fill all details")
            elif any(a['app_id'] == aid for a in apps):
                st.warning("App already in list!")
            else:
                apps.append({
                    "app_name": name,
                    "app_id": aid,
                    "hints": [h.strip() for h in hints.split(",") if h.strip()],
                    "added_on": datetime.now(IST_TZ).strftime("%Y-%m-%d")
                })
                save_json(APP_DB_PATH, apps)
                st.success("App Added Successfully!")

    if apps:
        st.write("### Registered Apps")
        st.table(pd.DataFrame(apps)[["app_name", "app_id", "added_on"]])

# --- MAIN NAVIGATION ---
ensure_db_files()
if "page" not in st.session_state: st.session_state.page = "home"

if st.session_state.page == "home":
    st.title("RW Review Intelligence")
    st.write("Select a module to start checking.")
    c1, c2 = st.columns(2)
    if c1.button("📊 Make List (Manual)"): 
        st.session_state.page = "manual"; st.rerun()
    if c2.button("⚙️ Add App (Settings)"): 
        st.session_state.page = "add_app"; st.rerun()
else:
    if st.button("⬅️ Back to Menu"):
        st.session_state.page = "home"; st.rerun()

if st.session_state.page == "manual": render_manual_page()
elif st.session_state.page == "add_app": render_add_app_page()
