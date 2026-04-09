import io
import json
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import pytz
import streamlit as st
from google_play_scraper import Sort, reviews

# 1. Page Config
st.set_page_config(page_title="RW Pro Live Checker", page_icon="🚀", layout="wide")

# 2. UI Styling
st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem !important; }
    .stDataFrame td { white-space: normal !important; word-wrap: break-word !important; }
    .stButton > button { width: 100% !important; font-weight: bold !important; border-radius: 8px !important; }
    .small-counter {
        border: 1px solid #2ecc71;
        background-color: #f0fff4;
        padding: 8px 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        display: inline-block;
    }
    .small-counter b { color: #16a34a; font-size: 18px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- HEADER ---
logo_url = "https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png"
st.markdown(
    f"""
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <img src="{logo_url}" width="50">
        <h2 style="margin: 0;">RW Pro Live Checker</h2>
    </div>
""",
    unsafe_allow_html=True,
)

IST_TZ = pytz.timezone("Asia/Kolkata")
DATA_DIR = "data"
APP_DB_PATH = os.path.join(DATA_DIR, "apps_config.json")
DAILY_DB_PATH = os.path.join(DATA_DIR, "daily_reports.json")


# --------- Helpers ---------
def ensure_db_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(APP_DB_PATH):
        with open(APP_DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
    if not os.path.exists(DAILY_DB_PATH):
        with open(DAILY_DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_id(url):
    if not url or "play.google.com" not in url:
        return None
    match = re.search(r"id=([a-zA-Z0-9._]+)", url)
    return match.group(1) if match else None


def normalize_csv_values(raw):
    if not raw.strip():
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def review_matches_hint(text, hints):
    if not hints:
        return True
    stripped = text.strip()
    return any(stripped.endswith(hint) for hint in hints)


def fetch_logic(aid, target_dt, depth, star_values=None, hint_values=None):
    all_raw = []
    token = None
    for _ in range(depth):
        try:
            res, token = reviews(
                aid,
                lang="en",
                country="in",
                sort=Sort.NEWEST,
                count=100,
                continuation_token=token,
            )
            if not res:
                break
            all_raw.extend(res)
            last_dt = res[-1]["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()
            if last_dt < target_dt:
                break
            if not token:
                break
        except Exception:
            break

    stars_set = set(star_values or [])
    matches = []
    for r in all_raw:
        rev_time = r["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ)
        if rev_time.date() != target_dt:
            continue

        if stars_set and int(r.get("score", 0)) not in stars_set:
            continue

        text = (r.get("content") or "").strip()
        if not review_matches_hint(text, hint_values or []):
            continue

        matches.append(
            {
                "User": r.get("userName", "Unknown"),
                "Review": text,
                "App ID": aid,
                "Rating": f"{r.get('score', 0)}/5",
                "Date": rev_time.strftime("%Y-%m-%d"),
                "Time": rev_time.strftime("%H:%M:%S"),
            }
        )
    return matches


def build_compact_df(report_items):
    rows = []
    for item in report_items:
        users_sorted = sorted(item.get("users", []), key=lambda x: x.lower())
        for user in users_sorted:
            rows.append(
                {
                    "App Name": item["app_name"],
                    "Date": item["report_date"],
                    "Hints": ", ".join(item.get("hints", [])) if item.get("hints") else "-",
                    "User": user,
                }
            )
    return pd.DataFrame(rows)


def build_pdf_text_blob(report_items):
    out_lines = []
    for item in report_items:
        out_lines.append(f"{item['app_name']} ({item['report_date']}):")
        hint_txt = ", ".join(item.get("hints", [])) if item.get("hints") else "No hint"
        out_lines.append(f"Hint: {hint_txt}")

        users_sorted = sorted(item.get("users", []), key=lambda x: x.lower())
        if users_sorted:
            for idx, user in enumerate(users_sorted, start=1):
                out_lines.append(f"{idx}. {user}")
        else:
            out_lines.append("No users found")
        out_lines.append("")
    return "\n".join(out_lines)


def run_due_daily_jobs(scan_depth):
    apps = load_json(APP_DB_PATH)
    reports = load_json(DAILY_DB_PATH)

    report_index = {(r["app_id"], r["report_date"]) for r in reports}
    now_ist = datetime.now(IST_TZ)
    generated = 0

    for app in apps:
        created_dt = datetime.fromisoformat(app["created_at"])
        due_date = (created_dt + timedelta(days=app.get("days_after", 7))).date()
        run_h, run_m = [int(p) for p in app.get("run_time", "20:00").split(":")]
        due_dt = IST_TZ.localize(datetime(due_date.year, due_date.month, due_date.day, run_h, run_m))

        report_key = (app["app_id"], due_date.strftime("%Y-%m-%d"))
        if now_ist < due_dt or report_key in report_index:
            continue

        found = fetch_logic(
            app["app_id"],
            due_date,
            scan_depth,
            star_values=app.get("stars", []),
            hint_values=app.get("hints", []),
        )

        users = sorted({x["User"] for x in found}, key=lambda x: x.lower())
        reports.append(
            {
                "app_id": app["app_id"],
                "app_name": app["app_name"],
                "report_date": due_date.strftime("%Y-%m-%d"),
                "hints": app.get("hints", []),
                "stars": app.get("stars", []),
                "users": users,
                "detailed_rows": found,
                "generated_at": now_ist.isoformat(),
            }
        )
        generated += 1

    if generated:
        save_json(DAILY_DB_PATH, reports)
    return generated


def render_manual_page():
    st.subheader("Make List (Manual Method)")
    st.caption("Same live/manual scan flow, with single or bulk URL support.")

    if "manual_bulk_mode" not in st.session_state:
        st.session_state.manual_bulk_mode = False
    if "manual_matches" not in st.session_state:
        st.session_state.manual_matches = []
    if "manual_summary" not in st.session_state:
        st.session_state.manual_summary = {}

    colm1, _ = st.columns([1, 2])
    with colm1:
        if st.button("🔄 Switch Single/Bulk"):
            st.session_state.manual_bulk_mode = not st.session_state.manual_bulk_mode
            st.session_state.manual_matches = []
            st.session_state.manual_summary = {}

    st.sidebar.header("⚙️ Manual Mode Configuration")
    if st.session_state.manual_bulk_mode:
        bulk_links = st.sidebar.text_area("Bulk Links (One per line):", height=150)
        app_url = ""
    else:
        app_url = st.sidebar.text_input(
            "Play Store URL:",
            value="https://play.google.com/store/apps/details?id=com.ideopay.user",
        )
        bulk_links = ""

    scan_depth = st.sidebar.select_slider("Scan Depth (Pages)", options=[1, 10, 50, 100, 200, 500], value=100)
    score_filter = st.sidebar.selectbox("Filter Stars", [None, 5, 4, 3, 2, 1], index=0)
    target_date = st.sidebar.date_input("Select Date", datetime.now(IST_TZ).date())

    hint_type = st.sidebar.radio("Hint Mode", ["Show All", "No Hint (Normal .)", "Custom Symbol"], index=2)
    custom_symbol = ""
    if hint_type == "Custom Symbol":
        custom_symbol = st.sidebar.text_input("Enter Symbol (e.g. # or ,,)", value="#")

    if st.button("🚀 Run Professional Check"):
        urls = [u.strip() for u in (bulk_links.split("\n") if st.session_state.manual_bulk_mode else [app_url]) if u.strip()]
        st.session_state.manual_matches = []
        st.session_state.manual_summary = {}

        if not urls:
            st.warning("Please add at least one app link.")
            return

        progress_bar = st.progress(0)
        for i, url in enumerate(urls):
            aid = extract_id(url)
            if aid:
                with st.spinner(f"Scanning {aid}..."):
                    hints = []
                    if hint_type == "Custom Symbol" and custom_symbol:
                        hints = [custom_symbol]
                    found = fetch_logic(
                        aid,
                        target_date,
                        scan_depth,
                        star_values=[score_filter] if score_filter else [],
                        hint_values=hints,
                    )

                    if hint_type == "No Hint (Normal .)":
                        found = [
                            x
                            for x in found
                            if (x["Review"].endswith(".") and not x["Review"].endswith(".."))
                            or (len(x["Review"]) > 0 and x["Review"][-1].isalnum())
                        ]

                    st.session_state.manual_matches.extend(found)
                    st.session_state.manual_summary[aid] = len(found)
            progress_bar.progress((i + 1) / len(urls))
        st.toast("✅ Scan Complete!", icon="🎉")

    if st.session_state.manual_summary:
        st.markdown(
            f'<div class="small-counter">Total Live: <b>{len(st.session_state.manual_matches)}</b></div>',
            unsafe_allow_html=True,
        )

        if st.session_state.manual_matches:
            df = pd.DataFrame(st.session_state.manual_matches)
            st.dataframe(df, use_container_width=True)

        st.markdown("### 📊 Summary")
        st.table(pd.DataFrame(list(st.session_state.manual_summary.items()), columns=["App ID", "Count"]))

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            start_row = 0
            for aid in st.session_state.manual_summary.keys():
                app_data = [m for m in st.session_state.manual_matches if m["App ID"] == aid]
                if app_data:
                    pd.DataFrame(app_data).to_excel(writer, index=False, sheet_name="Data", startrow=start_row)
                    start_row += len(app_data) + 2

        file_date = target_date.strftime("%Y-%m-%d")
        if st.session_state.manual_bulk_mode:
            fname = f"Bulk_Report_{file_date}.xlsx"
        else:
            aid_label = extract_id(app_url) if extract_id(app_url) else "Report"
            fname = f"{aid_label}_{file_date}.xlsx"

        st.download_button("📥 Excel Report", output.getvalue(), fname, use_container_width=True)


def render_add_app_page():
    st.subheader("Add App (Admin Panel)")
    st.caption("Add app link with hints and star filters in single or bulk mode.")

    apps = load_json(APP_DB_PATH)

    single_tab, bulk_tab = st.tabs(["Single Add", "Bulk Add"])

    with single_tab:
        with st.form("single_add_form", clear_on_submit=True):
            app_name = st.text_input("App Name")
            app_url = st.text_input("Play Store Link")
            hints_raw = st.text_input("Hints (comma separated, e.g. #, *, @@)")
            stars_raw = st.text_input("Stars (comma separated, e.g. 5,4)")
            days_after = st.number_input("Generate list after days", min_value=1, value=7)
            run_time = st.text_input("Daily run time (HH:MM, IST)", value="20:00")
            submitted = st.form_submit_button("Save App")

        if submitted:
            aid = extract_id(app_url)
            if not app_name.strip() or not aid:
                st.error("Please enter valid app name and Play Store link.")
            else:
                hints = normalize_csv_values(hints_raw)
                stars = [int(s) for s in normalize_csv_values(stars_raw) if s.isdigit() and 1 <= int(s) <= 5]

                apps.append(
                    {
                        "app_name": app_name.strip(),
                        "app_url": app_url.strip(),
                        "app_id": aid,
                        "hints": hints,
                        "stars": stars,
                        "days_after": int(days_after),
                        "run_time": run_time.strip() if run_time.strip() else "20:00",
                        "created_at": datetime.now(IST_TZ).isoformat(),
                    }
                )
                save_json(APP_DB_PATH, apps)
                st.success("App added successfully.")

    with bulk_tab:
        st.markdown("Bulk format per line: `App Name|PlayStore URL|hint1,hint2|5,4|7|20:00`")
        bulk_text = st.text_area("Paste bulk lines", height=200)
        if st.button("Save Bulk Apps"):
            lines = [ln.strip() for ln in bulk_text.split("\n") if ln.strip()]
            added = 0
            for line in lines:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 2:
                    continue
                app_name = parts[0]
                app_url = parts[1]
                aid = extract_id(app_url)
                if not app_name or not aid:
                    continue

                hints = normalize_csv_values(parts[2]) if len(parts) >= 3 else []
                stars_raw = normalize_csv_values(parts[3]) if len(parts) >= 4 else []
                stars = [int(s) for s in stars_raw if s.isdigit() and 1 <= int(s) <= 5]
                days_after = int(parts[4]) if len(parts) >= 5 and parts[4].isdigit() else 7
                run_time = parts[5] if len(parts) >= 6 and re.match(r"^\d{2}:\d{2}$", parts[5]) else "20:00"

                apps.append(
                    {
                        "app_name": app_name,
                        "app_url": app_url,
                        "app_id": aid,
                        "hints": hints,
                        "stars": stars,
                        "days_after": days_after,
                        "run_time": run_time,
                        "created_at": datetime.now(IST_TZ).isoformat(),
                    }
                )
                added += 1

            save_json(APP_DB_PATH, apps)
            st.success(f"Added {added} app(s).")

    st.markdown("### Stored Apps")
    apps_df = pd.DataFrame(apps)
    st.dataframe(apps_df, use_container_width=True)


def render_daily_list_page():
    st.subheader("Daily List")
    st.caption("Auto-create scheduled lists after configured day gap and 8:00 PM (or custom time) in IST.")

    scan_depth = st.select_slider("Scan Depth (for auto jobs)", options=[1, 10, 50, 100, 200], value=100)
    if st.button("Run Pending Daily Jobs Now"):
        count = run_due_daily_jobs(scan_depth)
        st.success(f"Generated {count} new list(s).")

    reports = load_json(DAILY_DB_PATH)
    if not reports:
        st.info("No daily list generated yet.")
        return

    summary_rows = [
        {
            "App Name": r["app_name"],
            "App ID": r["app_id"],
            "Date": r["report_date"],
            "Users": len(r.get("users", [])),
            "Hints": ", ".join(r.get("hints", [])) if r.get("hints") else "-",
            "Generated At": r.get("generated_at", ""),
        }
        for r in reports
    ]

    st.markdown("### Generated Lists")
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

    detailed_rows = []
    for r in reports:
        detailed_rows.extend(r.get("detailed_rows", []))

    if detailed_rows:
        detailed_df = pd.DataFrame(detailed_rows)
        detailed_buffer = io.BytesIO()
        detailed_df.to_excel(detailed_buffer, index=False)
        st.download_button(
            "📥 Download Detailed Excel",
            detailed_buffer.getvalue(),
            file_name=f"daily_detailed_{datetime.now(IST_TZ).strftime('%Y-%m-%d')}.xlsx",
            use_container_width=True,
        )

    compact_df = build_compact_df(reports)
    if not compact_df.empty:
        compact_df = compact_df.sort_values(by=["App Name", "Date", "User"])

        compact_buffer = io.BytesIO()
        compact_df.to_excel(compact_buffer, index=False)
        st.download_button(
            "📥 Download Compact Excel (App, Date, Hint, User)",
            compact_buffer.getvalue(),
            file_name=f"daily_compact_{datetime.now(IST_TZ).strftime('%Y-%m-%d')}.xlsx",
            use_container_width=True,
        )

        pdf_text = build_pdf_text_blob(reports)
        st.download_button(
            "📥 Download PDF Format (text layout)",
            data=pdf_text.encode("utf-8"),
            file_name=f"daily_list_{datetime.now(IST_TZ).strftime('%Y-%m-%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        st.markdown("### Preview Format")
        st.text(pdf_text)


# --------- Main navigation ---------
ensure_db_files()

if "home_page" not in st.session_state:
    st.session_state.home_page = "home"

if st.session_state.home_page == "home":
    st.subheader("Homepage")
    c1, c2, c3 = st.columns(3)
    if c1.button("Make List"):
        st.session_state.home_page = "manual"
        st.rerun()
    if c2.button("Add App"):
        st.session_state.home_page = "add_app"
        st.rerun()
    if c3.button("Daily List"):
        st.session_state.home_page = "daily"
        st.rerun()

else:
    if st.button("⬅️ Back to Homepage"):
        st.session_state.home_page = "home"
        st.rerun()

    if st.session_state.home_page == "manual":
        render_manual_page()
    elif st.session_state.home_page == "add_app":
        render_add_app_page()
    elif st.session_state.home_page == "daily":
        render_daily_list_page()
