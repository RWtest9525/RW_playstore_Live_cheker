import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews_all
from datetime import datetime

# Page Config
st.set_page_config(page_title="RW play store live cheker", page_icon="📊", layout="wide")

# CSS to fix text wrapping (Full comments) and sidebar styling
st.markdown("""
    <style>
    .stDataFrame td {
        white-space: normal !important;
        word-wrap: break-word !important;
        line-height: 1.5 !important;
        vertical-align: top !important;
    }
    /* Makes the input text clear and blue */
    .stTextInput > div > div > input {
        color: #4F8BF9;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 RW play store live cheker")

# --- SIDEBAR ---
st.sidebar.header("Settings")
# 1. Blank by default - No Link
app_url = st.sidebar.text_input("Paste Play Store URL:", value="", placeholder="Paste link here...") 

score_filter = st.sidebar.selectbox("Filter by Stars", [None, 5, 4, 3, 2, 1], format_func=lambda x: "Show All" if x is None else f"{x} Stars")

st.sidebar.subheader("Date Filter")
use_date = st.sidebar.checkbox("Filter by Specific Date")
target_date = st.sidebar.date_input("Select Date", datetime.now())

st.sidebar.subheader("Hint Logic")
hint_type = st.sidebar.radio("Hint Type", ["Show All", "No Hint (Normal .)", "Custom Symbol"])

# 2. Blank by default - No Hint Symbol
custom_symbol = ""
if hint_type == "Custom Symbol":
    custom_symbol = st.sidebar.text_input("Enter Symbol", value="", placeholder="Leave blank or enter symbol...")
    st.sidebar.caption("⌨️ Tip: Press Win + . to open emoji picker")

def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

if st.button("🚀 Fetch All Available Reviews"):
    app_id = extract_id(app_url)
    
    if app_id:
        with st.spinner("Searching through all reviews..."):
            try:
                # Fetching ALL data available
                res = reviews_all(
                    app_id,
                    lang='en',
                    country='us',
                    sort=Sort.NEWEST,
                    filter_score_with=score_filter
                )
                
                final_list = []
                for r in res:
                    # Clean data extraction
                    raw_content = str(r['content']).strip()
                    user_name = str(r['userName']).strip()
                    review_date = r['at'].date()
                    
                    # Date Filtering
                    if use_date and review_date != target_date:
                        continue
                    
                    # Hint Filtering Logic
                    if hint_type == "Show All":
                        keep = True
                    elif hint_type == "No Hint (Normal .)":
                        # Logic: Ends with dot or a normal letter/number
                        keep = raw_content.endswith('.') or (len(raw_content) > 0 and raw_content[-1].isalnum())
                    else:
                        # Custom Symbol logic: If box is blank, show all. If symbol entered, filter by it.
                        if custom_symbol == "":
                            keep = True
                        else:
                            keep = raw_content.endswith(custom_symbol)
                    
                    if keep:
                        final_list.append({
                            "Date": r['at'].strftime('%Y-%m-%d %H:%M:%S'),
                            "User": user_name,
                            "Rating": r['score'],
                            "Review": raw_content
                        })

                if final_list:
                    df = pd.DataFrame(final_list)
                    st.success(f"Success! Found {len(df)} matching reviews.")
                    
                    # Display table with full wrapping
                    st.dataframe(df, use_container_width=True)
                    
                    # CSV Download (Fixes Excel Date ####### issue)
                    csv_data = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Results",
                        data=csv_data,
                        file_name=f"{app_id}_export.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("No reviews found. Try changing the Star filter or Date.")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.error("Please paste a Play Store link first.")
