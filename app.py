import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews
from datetime import datetime

# Page Config
st.set_page_config(page_title="RW play store live cheker", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .stDataFrame td { white-space: normal !important; word-wrap: break-word !important; line-height: 1.5 !important; vertical-align: top !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 RW play store live cheker")

# Initialize session state to store reviews and tokens for "Set 2, 3..."
if 'all_matches' not in st.session_state:
    st.session_state.all_matches = []
if 'token' not in st.session_state:
    st.session_state.token = None

# --- SIDEBAR ---
st.sidebar.header("Settings")
app_url = st.sidebar.text_input("Paste Play Store URL:", value="") 
count = st.sidebar.slider("Batch Size (Per Set)", 10, 1000, 500)
score_filter = st.sidebar.selectbox("Filter by Stars", [None, 5, 4, 3, 2, 1], format_func=lambda x: "Show All" if x is None else f"{x} Stars")

st.sidebar.subheader("Date Filter")
use_date = st.sidebar.checkbox("Filter by Specific Date")
target_date = st.sidebar.date_input("Select Date", datetime.now())

st.sidebar.subheader("Hint Logic")
hint_type = st.sidebar.radio("Hint Type", ["Show All", "No Hint (Normal .)", "Custom Symbol"])
custom_symbol = st.sidebar.text_input("Enter Symbol", value="") if hint_type == "Custom Symbol" else ""

def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

# --- BUTTONS ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🚀 New Search (Start Set 1)"):
        st.session_state.all_matches = []
        st.session_state.token = None
        app_id = extract_id(app_url)
        
        if app_id:
            with st.spinner("Fetching Set 1..."):
                res, token = reviews(app_id, lang='en', country='us', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
                st.session_state.token = token
                
                for r in res:
                    content = r['content'].strip()
                    if use_date and r['at'].date() != target_date: continue
                    
                    keep = False
                    if hint_type == "Show All": keep = True
                    elif hint_type == "No Hint (Normal .)":
                        if len(content) > 0:
                            if content.endswith('.'): keep = not content.endswith('..')
                            else: keep = content[-1].isalnum()
                    else: keep = content.endswith(custom_symbol) if custom_symbol else True
                    
                    if keep:
                        st.session_state.all_matches.append({"Date": r['at'].strftime('%Y-%m-%d %H:%M:%S'), "User": r['userName'], "Rating": r['score'], "Review": r['content']})
        else:
            st.error("Please enter a valid link.")

with col2:
    # Only show "Fetch Next Set" if we have a token from a previous search
    if st.session_state.token:
        if st.button("➕ Fetch Next Set (Deep Scan)"):
            app_id = extract_id(app_url)
            with st.spinner("Fetching more reviews..."):
                res, token = reviews(app_id, continuation_token=st.session_state.token)
                st.session_state.token = token
                
                for r in res:
                    content = r['content'].strip()
                    if use_date and r['at'].date() != target_date: continue
                    
                    keep = False
                    if hint_type == "Show All": keep = True
                    elif hint_type == "No Hint (Normal .)":
                        if len(content) > 0:
                            if content.endswith('.'): keep = not content.endswith('..')
                            else: keep = content[-1].isalnum()
                    else: keep = content.endswith(custom_symbol) if custom_symbol else True
                    
                    if keep:
                        st.session_state.all_matches.append({"Date": r['at'].strftime('%Y-%m-%d %H:%M:%S'), "User": r['userName'], "Rating": r['score'], "Review": r['content']})

# --- DISPLAY RESULTS ---
if st.session_state.all_matches:
    df = pd.DataFrame(st.session_state.all_matches)
    st.success(f"Total Matches Found so far: {len(df)}")
    st.dataframe(df, use_container_width=True)
    
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(label="📥 Download Results", data=csv_data, file_name="export.csv", mime="text/csv")
elif app_url:
    st.info("No matches found in this set. Try clicking 'Fetch Next Set' to look further back in time.")
