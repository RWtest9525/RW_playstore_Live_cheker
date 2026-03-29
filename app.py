import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews
from datetime import datetime

# Page Config
st.set_page_config(page_title="Live Play Store Review Extractor", layout="wide")

st.title("📱 Live Google Play Review Extractor")
st.markdown("Extract, filter by stars, and find custom 'hint' symbols in real-time.")

# --- SIDEBAR SETTINGS ---
st.sidebar.header("Settings")
app_url = st.sidebar.text_input("Paste Play Store URL:", "https://play.google.com/store/apps/details?id=com.whatsapp")
count = st.sidebar.slider("Number of reviews to scan", 10, 500, 100)
score_filter = st.sidebar.selectbox("Filter by Stars", [None, 5, 4, 3, 2, 1], format_func=lambda x: "Show All" if x is None else f"{x} Stars")

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
            # Fetch reviews
            res, _ = reviews(
                app_id,
                lang='en',
                country='us',
                sort=Sort.NEWEST,
                count=count,
                filter_score_with=score_filter
            )
            
            # Apply Hint Logic
            final_list = []
            for r in res:
                content = r['content'].strip()
                
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

            # --- DISPLAY & DOWNLOAD ---
            if final_list:
                df = pd.DataFrame(final_list)
                st.success(f"Found {len(df)} matching reviews!")
                
                # Show Data
                st.dataframe(df, use_container_width=True)
                
                # Excel Download
                excel_file = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=excel_file,
                    file_name=f"reviews_{app_id}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No reviews matched your filters. Try increasing the scan count or changing the symbol.")
    else:
        st.error("Invalid URL. Please check the Play Store link.")
