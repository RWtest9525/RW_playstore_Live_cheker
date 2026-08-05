import io
import json
import os
import re
from datetime import datetime
import pandas as pd
import pytz
import streamlit as st
from google_play_scraper import Sort, reviews

# 1. Page Config & Professional UI
st.set_page_config(page_title="RW Live Checker", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #01875f !important;
        color: white !important;
        font-weight: bold;
    }
    .report-box {
        padding: 20px;
        border-radius: 10px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
    }
    .counter-text {
        font-size: 24px;
        font-weight: bold;
        color: #01875f;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIG ---
IST_TZ = pytz.timezone("Asia/Kolkata")

def extract_id(url):
    if not url: return None
    url = url.strip()
    if "id=" in url:
        match = re.search(r"id=([a-zA-Z0-9._]+)", url)
        return match.group(1) if match else url
    return url

# --- ACCURATE FETCH LOGIC ---
def fetch_reviews(aid, target_dt, star_filter, hint_val):
    all_raw = []
    token = None
    matches = []
    seen_combinations = set() # Safety for extra names
    
    # 2000 depth means it can scan up to 2 lakh reviews - No loss possible
    for _ in range(2000):
        try:
            res, token = reviews(
                aid, lang="en", country="in", 
                sort=Sort.NEWEST, count=100, 
                continuation_token=token
            )
            if not res: break
            all_raw.extend(res)
            
            # Check if we crossed the date
            last_date = res[-1]["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()
            if last_date < target_dt: break
            if not token: break
        except:
            break

    for r in all_raw:
        rev_dt = r["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()
        if rev_dt != target_dt: continue
        
        # Rating Filter
        if star_filter and int(r.get("score", 0)) != star_filter: continue

        text = (r.get("content") or "").strip()
        user = (r.get("userName") or "Unknown").strip()
        
        # Hint Check
        is_match = False
        if not hint_val:
            is_match = True
        else:
            h = hint_val.lower().strip()
            if text.lower().endswith(h) or user.lower().endswith(h):
                is_match = True
        
        if is_match:
            # COMBINATION KEY: Allows same name if review is different (No Loss)
            # Blocks only if EXACT same person and EXACT same review repeat
            unique_key = f"{user.lower()}|||{text.lower()}"
            if unique_key not in seen_combinations:
                matches.append({
                    "User": user,
                    "Review": text,
                    "Package ID": aid,
                    "Rating": f"{r.get('score', 0)}/5",
                    "Date": rev_dt.strftime("%Y-%m-%d"),
                    "Time": r["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).strftime("%H:%M:%S")
                })
                seen_combinations.add(unique_key)
                
    return matches

# --- UI MAIN ---
st.title("🚀 RW Play Store Live Checker")

# Top Input Section
with st.container():
    st.markdown('<div class="report-box">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
    
    with c1:
        app_input = st.text_input("Enter Play Store Link / Package ID", placeholder="com.example.app")
    with c2:
        target_date = st.date_input("Select Check Date", datetime.now(IST_TZ).date())
    with c3:
        star_sel = st.selectbox("Stars", [None, 5, 4, 3, 2, 1])
    with c4:
        hint_input = st.text_input("Hint (Ends With)", placeholder="e.g. #")
    
    run_btn = st.button("🔍 CHECK NOW")
    st.markdown('</div>', unsafe_allow_html=True)

# Processing
if run_btn:
    aid = extract_id(app_input)
    if not aid:
        st.error("Please enter a valid Link or Package ID")
    else:
        with st.spinner(f"Scanning {aid}... Please wait."):
            results = fetch_reviews(aid, target_date, star_sel, hint_input)
            st.session_state.current_data = results
            st.session_state.current_aid = aid

# Display Results
if "current_data" in st.session_state:
    data = st.session_state.current_data
    aid = st.session_state.current_aid
    
    st.markdown(f"### Results for: `{aid}`")
    st.markdown(f'<div class="counter-text">Total Live: {len(data)}</div>', unsafe_allow_html=True)
    
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, height=500)
        
        # Simple Download Button
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        st.download_button(
            label="📥 DOWNLOAD EXCEL REPORT",
            data=output.getvalue(),
            file_name=f"Live_{aid}_{target_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No reviews found for this date/filter.")

st.divider()
st.caption("RW Digital Team - Professional Version 2026")
