import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews
from datetime import datetime

# Page Config
st.set_page_config(page_title="RW play store live cheker", page_icon="📊", layout="wide")

# CSS to fix text wrapping for full comments
st.markdown("""
    <style>
    .stDataFrame td {
        white-space: normal !important;
        word-wrap: break-word !important;
        line-height: 1.5 !important;
        vertical-align: top !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 RW play store live cheker")

# --- SIDEBAR ---
st.sidebar.header("Settings")
app_url = st.sidebar.text_input("Paste Play Store URL:", value="") 

# Restored the Slider for choosing how much data to scan
count = st.sidebar.slider("Number of reviews to scan", 10, 5000, 200)

score_filter = st.sidebar.selectbox("Filter by Stars", [None, 5, 4, 3, 2, 1], format_func=lambda x: "Show All" if x is None else f"{x} Stars")

st.sidebar.subheader("Date Filter")
use_date = st.sidebar.checkbox("Filter by Specific Date")
target_date = st.sidebar.date_input("Select Date", datetime.now())

st.sidebar.subheader("Hint Logic")
hint_type = st.sidebar.radio("Hint Type", ["Show All", "No Hint (Normal .)", "Custom Symbol"])

# Strictly blank symbol box
custom_symbol = ""
if hint_type == "Custom Symbol":
    custom_symbol = st.sidebar.text_input("Enter Symbol", value="")

def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

if st.button("🚀 Fetch Real-Time Reviews"):
    app_id = extract_id(app_url)
    
    if app_id:
        with st.spinner("Fetching data..."):
            try:
                # Using the stable 'reviews' method with the user's chosen count
                res, _ = reviews(
                    app_id,
                    lang='en',
                    country='us',
                    sort=Sort.NEWEST,
                    count=count,
                    filter_score_with=score_filter
                )
                
                final_list = []
                for r in res:
                    content = r['content']
                    review_date = r['at'].date()
                    
                    if use_date and review_date != target_date:
                        continue
                    
                    if hint_type == "Show All":
                        keep = True
                    elif hint_type == "No Hint (Normal .)":
