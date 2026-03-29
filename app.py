import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews
from datetime import datetime

# Page Config
st.set_page_config(page_title="Live Play Store Review Extractor", layout="wide")

st.title("📱 Live Google Play Review Extractor")
st.markdown("Extract, filter by stars, date, and find custom 'hint' symbols in real-time.")

# --- SIDEBAR SETTINGS ---
st.sidebar.header("Settings")
app_url = st.sidebar.text_input("Paste Play Store URL:", "https://play.google.com/store/apps/details?id=com.whatsapp")
count = st.sidebar.slider("Number of reviews to scan", 10, 1000, 200)
score_filter = st.sidebar.selectbox("Filter by Stars", [None, 5, 4, 3, 2, 1], format_func=lambda x: "Show All" if x is None else f"{x} Stars")

# --- NEW: DATE FILTER ---
st.sidebar.subheader("Date Filter")
use_date = st.sidebar.checkbox("Filter by Specific Date")
target_date = st.sidebar.date_input("Select Date", datetime.now())

st.sidebar.subheader("Hint Logic")
hint_type = st.sidebar.radio("Hint Type", ["Show All", "No Hint (Normal .)", "Custom Symbol"])
custom_symbol = ""
if hint_type == "Custom Symbol":
    custom_symbol = st.sidebar.text_input("Enter Symbol (e.g. !, #, *)", "!")

# --- PROCESSING ---
def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

if st.button("🚀 Fetch Live Reviews"):
    app_id = extract_id(app_url)
    
    if app_id:
        with st.spinner(f"Fetching data for {app_id}..."):
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
                content = r['content'].strip()
                review_date = r['at'].date()
                
                # 1. Date Check
                if use_date and review_date != target_date:
                    continue
                
                # 2. Hint Check
                if hint_type == "Show All":
                    keep = True
                elif hint_type == "No Hint (Normal .)":
                    keep = content.endswith('.') or content[-1].isalnum()
                else: # Custom Symbol
                    keep = content.endswith(custom_symbol)
                
                if keep:
                    final_list.append({
                        "Date": r['at'],
                        "User": r['userName'],
                        "Rating": r['score'],
                        "Review": r['content']
                    })

            if final_list:
                df = pd.DataFrame(final_list)
                st.success(f"Found {len(df)} matching reviews!")
                st.dataframe(df, use_container_width=True)
                
                excel_file = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=excel_file,
                    file_name=f"reviews_{app_id}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No reviews matched your filters. Try increasing the 'Number of reviews to scan' or changing the date.")
    else:
        st.error("Invalid URL. Please check the Play Store link.")
