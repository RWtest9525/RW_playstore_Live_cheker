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

# Stable Slider for choosing how much data to scan
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
                # Stable 'reviews' method
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
                    
                    # 1. Date Check
                    if use_date and review_date != target_date:
                        continue
                    
                    # 2. Hint Check (Fixing the Indentation Error here)
                    if hint_type == "Show All":
                        keep = True
                    elif hint_type == "No Hint (Normal .)":
                        clean_text = content.strip()
                        keep = clean_text.endswith('.') or (len(clean_text) > 0 and clean_text[-1].isalnum())
                    else:
                        # Custom Symbol Logic
                        if custom_symbol == "":
                            keep = True
                        else:
                            keep = content.strip().endswith(custom_symbol)
                    
                    if keep:
                        final_list.append({
                            "Date": r['at'].strftime('%Y-%m-%d %H:%M:%S'),
                            "User": r['userName'],
                            "Rating": r['score'],
                            "Review": content
                        })

                if final_list:
                    df = pd.DataFrame(final_list)
                    st.success(f"Matches Found: {len(df)}")
                    st.dataframe(df, use_container_width=True)
                    
                    csv_data = df.to_csv(index=False).encode('utf-8')
                    st.download_button(label="📥 Download Results", data=csv_data, file_name=f"{app_id}_export.csv", mime="text/csv")
                else:
                    st.warning("No matching reviews found for these filters.")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.error("Please enter a valid link.")
