import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews
from datetime import datetime
import pytz
import os

# 1. Page Config
st.set_page_config(page_title="RW play store live cheker", page_icon="🎯", layout="wide")

# 2. FIXED HEADER CSS (Single Line, Full Logo, Responsive)
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    
    /* Header Container - Forces logo and text together */
    .header-box {
        display: flex;
        align-items: center;
        margin-bottom: 25px;
        gap: 15px;
    }

    /* Logo Styling - No Cropping */
    .header-box img {
        height: 60px !important;
        width: auto !important;
        border-radius: 5px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    }

    /* Title Styling - No Wrap */
    .header-box h1 {
        margin: 0 !important;
        padding: 0 !important;
        font-size: clamp(22px, 4vw, 38px) !important;
        white-space: nowrap;
        color: white;
    }

    .stDataFrame td { white-space: normal !important; word-wrap: break-word !important; }
    .stButton > button { width: 100% !important; font-weight: bold !important; border-radius: 8px !important; }
    .status-done { color: #2ecc71; font-weight: bold; font-size: 20px; border: 2px solid #2ecc71; padding: 10px; border-radius: 10px; text-align: center; background-color: rgba(46, 204, 113, 0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- DISPLAY LOGO AND TITLE (LOCAL FILE METHOD) ---
logo_path = "logo.png"
if os.path.exists(logo_path):
    col_l, col_r = st.columns([1, 10]) # Using columns as a backup for flex
    with col_l:
        st.image(logo_path, width=70)
    with col_r:
        st.markdown("<h1 style='margin-top: 10px;'>RW play store live cheker</h1>", unsafe_allow_html=True)
else:
    st.title("📊 RW play store live cheker")

# 3. Initialize session state
if 'all_matches' not in st.session_state:
    st.session_state.all_matches = []
if 'token' not in st.session_state:
    st.session_state.token = None
if 'is_done' not in st.session_state:
    st.session_state.is_done = False

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuration")
app_url = st.sidebar.text_input("Play Store URL:", value="https://play.google.com/store/apps/details?id=com.sanatan.dharma")
count = st.sidebar.slider("Batch Size", 10, 1000, 500)
score_filter = st.sidebar.selectbox("Filter by Stars", [None, 5, 4, 3, 2, 1], format_func=lambda x: "Show All" if x is None else f"{x} Stars")

st.sidebar.subheader("📅 Date Filter")
use_date = st.sidebar.checkbox("Filter by Specific Date", value=True)

ist = pytz.timezone('Asia/Kolkata')
current_ist_time = datetime.now(ist)
target_date = st.sidebar.date_input("Select Date", current_ist_time)

st.sidebar.subheader("🔍 Hint Logic")
hint_type = st.sidebar.radio("Hint Type", ["Show All", "No Hint (Normal .)", "Custom Symbol"], index=2)
custom_symbol = st.sidebar.text_input("Enter Symbol", value="!") if hint_type == "Custom Symbol" else ""

def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else "App"

def process_reviews(res):
    new_matches = []
    ist_tz = pytz.timezone('Asia/Kolkata')
    for r in res:
        review_time_utc = r['at'].replace(tzinfo=pytz.utc)
        review_time_ist = review_time_utc.astimezone(ist_tz)
        review_date_ist = review_time_ist.date()
        content = r['content'].strip()

        if use_date and review_date_ist != target_date:
            continue

        keep = False
        if hint_type == "Show All":
            keep = True
        elif hint_type == "No Hint (Normal .)":
            if len(content) > 0:
                if content.endswith('.'):
                    keep = not content.endswith('..')
                else:
                    keep = content[-1].isalnum()
        else:
            keep = content.endswith(custom_symbol) if custom_symbol else True

        if keep:
            new_matches.append({
                "Date": review_time_ist.strftime('%Y-%m-%d %H:%M:%S'),
                "User": r['userName'],
                "Rating": r['score'],
                "Review": r['content']
            })
    return new_matches

# --- ACTION BUTTONS ---
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 Reset & Start Set 1"):
        st.session_state.all_matches = []
        st.session_state.token = None
        st.session_state.is_done = False
        app_id = extract_id(app_url)
        if app_url:
            with st.spinner("Fetching Data..."):
                res, token = reviews(app_id, lang='en', country='in', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
                st.session_state.token = token
                st.session_state.all_matches = process_reviews(res)
                if not token: st.session_state.is_done = True
        else:
            st.error("Invalid URL")

with col2:
    if st.session_state.token and not st.session_state.is_done:
        if st.button("Next Batch ➡️"):
            app_id = extract_id(app_url)
            with st.spinner("Loading..."):
                res, token = reviews(app_id, continuation_token=st.session_state.token)
                st.session_state.token = token
                st.session_state.all_matches.extend(process_reviews(res))
                if not token: st.session_state.is_done = True

# --- SIDEBAR QUICK COPY ---
if st.session_state.all_matches:
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Quick Copy")
    app_id_label = extract_id(app_url)
    date_display = target_date.strftime('%d %B %Y')
    copy_text = f"{app_id_label} ({date_display}) :\n"
    for i, m in enumerate(st.session_state.all_matches, 1):
        copy_text += f"{i}. {m['User']}: {m['Review']}\n"
    st.sidebar.text_area("Select All & Copy:", value=copy_text, height=300)

# --- RESULTS & DYNAMIC DOWNLOAD ---
if st.session_state.is_done:
    st.markdown('<div class="status-done">✅ ALL REVIEWS SCANNED</div>', unsafe_allow_html=True)

if st.session_state.all_matches:
    df = pd.DataFrame(st.session_state.all_matches)
    st.success(f"Matches: {len(df)}")
    st.dataframe(df, use_container_width=True)
    
    # DOWNLOAD FILENAME: AppID_Date.csv
    app_id_name = extract_id(app_url)
    formatted_date = target_date.strftime('%Y-%m-%d')
    final_filename = f"{app_id_name}_{formatted_date}.csv"
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Report", data=csv, file_name=final_filename, mime='text/csv')
