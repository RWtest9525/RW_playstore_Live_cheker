import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews
from datetime import datetime
import pytz  # Added for timezone handling

# Page Config
st.set_page_config(page_title="RW play store live cheker", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .stDataFrame td {
        white-space: normal !important;
        word-wrap: break-word !important;
        line-height: 1.5 !important;
        vertical-align: top !important;
    }
    .status-done {
        color: green;
        font-weight: bold;
        font-size: 20px;
        border: 2px solid green;
        padding: 10px;
        border-radius: 5px;
        text-align: center;
        margin-bottom: 20px;
    }
    .stButton > button {
        width: 100% !important;
        border-radius: 20px !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 RW play store live cheker")

# Initialize session state
if 'all_matches' not in st.session_state:
    st.session_state.all_matches = []
if 'token' not in st.session_state:
    st.session_state.token = None
if 'is_done' not in st.session_state:
    st.session_state.is_done = False

# --- SIDEBAR ---
st.sidebar.header("Settings")
app_url = st.sidebar.text_input("Paste Play Store URL:", value="")
count = st.sidebar.slider("Batch Size (Per Set)", 10, 1000, 500)
score_filter = st.sidebar.selectbox("Filter by Stars", [None, 5, 4, 3, 2, 1], 
                                    format_func=lambda x: "Show All" if x is None else f"{x} Stars")

st.sidebar.subheader("Date Filter")
use_date = st.sidebar.checkbox("Filter by Specific Date")

# FIX: Set default date to India Standard Time (IST)
ist = pytz.timezone('Asia/Kolkata')
current_ist_time = datetime.now(ist)
target_date = st.sidebar.date_input("Select Date", current_ist_time)

st.sidebar.subheader("Hint Logic")
hint_type = st.sidebar.radio("Hint Type", ["Show All", "No Hint (Normal .)", "Custom Symbol"])
custom_symbol = st.sidebar.text_input("Enter Symbol", value="") if hint_type == "Custom Symbol" else ""

def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

def process_reviews(res):
    new_matches = []
    for r in res:
        # Get the date of the review
        review_date = r['at'].date()
        content = r['content'].strip()

        # FIX: Strict date comparison
        if use_date and review_date != target_date:
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
                "Date": r['at'].strftime('%Y-%m-%d %H:%M:%S'),
                "User": r['userName'],
                "Rating": r['score'],
                "Review": r['content']
            })
    return new_matches

# --- NAVIGATION BUTTONS ---
col1, col2 = st.columns(2)

with col1:
    if st.button("< Reset & Start Set 1"):
        st.session_state.all_matches = []
        st.session_state.token = None
        st.session_state.is_done = False
        app_id = extract_id(app_url)
        if app_id:
            with st.spinner("Fetching Set 1..."):
                res, token = reviews(app_id, lang='en', country='us', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
                st.session_state.token = token
                st.session_state.all_matches = process_reviews(res)
                if not token:
                    st.session_state.is_done = True
        else:
            st.error("Please enter a valid link.")

with col2:
    if st.session_state.token and not st.session_state.is_done:
        if st.button("Fetch Next Set >"):
            app_id = extract_id(app_url)
            with st.spinner("Moving to Next Set..."):
                res, token = reviews(app_id, continuation_token=st.session_state.token)
                st.session_state.token = token
                st.session_state.all_matches.extend(process_reviews(res))
                if not token:
                    st.session_state.is_done = True

# --- STATUS ---
if st.session_state.is_done:
    st.markdown('<div class="status-done">✅ ALL DONE! All available reviews have been scanned.</div>', unsafe_allow_html=True)

# --- RESULTS ---
if st.session_state.all_matches:
    df = pd.DataFrame(st.session_state.all_matches)
    st.success(f"Matches Found: {len(df)}")
    st.dataframe(df, use_container_width=True)
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(label="📥 Download ALL Matches", data=csv_data, file_name="full_report.csv", mime="text/csv")
