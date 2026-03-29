import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews_all
from datetime import datetime

# Page Config
st.set_page_config(page_title="RW play store live cheker", page_icon="📊", layout="wide")

# CSS to fix the "Cut off" comments by forcing text wrapping
st.markdown("""
    <style>
    .stDataFrame td {
        white-space: normal !important;
        word-wrap: break-word !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 RW play store live cheker")

# --- SIDEBAR SETTINGS ---
st.sidebar.header("Settings")
# Removed default link
app_url = st.sidebar.text_input("Paste Play Store URL:", "") 

score_filter = st.sidebar.selectbox("Filter by Stars", [None, 5, 4, 3, 2, 1], format_func=lambda x: "Show All" if x is None else f"{x} Stars")

st.sidebar.subheader("Date Filter")
use_date = st.sidebar.checkbox("Filter by Specific Date")
target_date = st.sidebar.date_input("Select Date", datetime.now())

st.sidebar.subheader("Hint Logic")
hint_type = st.sidebar.radio("Hint Type", ["Show All", "No Hint (Normal .)", "Custom Symbol"])
custom_symbol = ""
if hint_type == "Custom Symbol":
    custom_symbol = st.sidebar.text_input("Enter Symbol", "!")

def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

if st.button("🚀 Fetch All Available Reviews"):
    app_id = extract_id(app_url)
    
    if app_id:
        with st.spinner("Fetching ALL reviews. This may take a minute for large apps..."):
            # Using reviews_all to get maximum data available
            res = reviews_all(
                app_id,
                lang='en',
                country='us',
                sort=Sort.NEWEST,
                filter_score_with=score_filter
            )
            
            final_list = []
            for r in res:
                content = r['content'].strip()
                review_date = r['at'].date()
                
                if use_date and review_date != target_date:
                    continue
                
                if hint_type == "Show All":
                    keep = True
                elif hint_type == "No Hint (Normal .)":
                    keep = content.endswith('.') or (len(content) > 0 and content[-1].isalnum())
                else:
                    keep = content.endswith(custom_symbol)
                
                if keep:
                    # Formatting date as string to fix the ###### Excel issue
                    final_list.append({
                        "Date": r['at'].strftime('%Y-%m-%d %H:%M:%S'),
                        "User": r['userName'],
                        "Rating": r['score'],
                        "Review": r['content']
                    })

            if final_list:
                df = pd.DataFrame(final_list)
                st.success(f"Done! Found {len(df)} matching reviews.")
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Results", csv, f"{app_id}_reviews.csv", "text/csv")
            else:
                st.warning("No matching reviews found in the entire history.")
    else:
        st.error("Please enter a valid Play Store URL.")
