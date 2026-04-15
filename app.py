def review_matches_hint(text, hints):
    if not hints:
        return True

    stripped = text.strip().lower()

    return any(
        stripped.endswith(h.strip().lower()) or
        stripped.endswith(h.strip().lower() + ".") or
        stripped.endswith(h.strip().lower() + " ")
        for h in hints
    )


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
                count=200,  # increased fetch size
                continuation_token=token,
            )

            if not res:
                break

            all_raw.extend(res)

            last_dt = res[-1]["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()

            # ✅ smart stop (avoid missing data)
            if last_dt < (target_dt - timedelta(days=2)):
                break

            if not token:
                break

        except Exception as e:
            print("FETCH ERROR:", e)
            break

    stars_set = set(star_values or [])
    matches = []

    for r in all_raw:
        try:
            rev_time = r["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ)

            # ✅ flexible date matching (fix 0 live issue)
            if rev_time.date() not in [
                target_dt,
                target_dt - timedelta(days=1),
                target_dt + timedelta(days=1),
            ]:
                continue

            if stars_set and int(r.get("score", 0)) not in stars_set:
                continue

            text = (r.get("content") or "").strip()
            if not text:
                continue

            if not review_matches_hint(text, hint_values or []):
                continue

            username = (r.get("userName") or "Unknown").strip()

            # ✅ remove fake / garbage users
            if username.lower() in ["a google user", "unknown"]:
                continue

            if not re.match(r"^[A-Za-z0-9 ._-]{3,50}$", username):
                continue

            matches.append(
                {
                    "User": username,
                    "Review": text,
                    "App ID": aid,
                    "Rating": f"{r.get('score', 0)}/5",
                    "Date": rev_time.strftime("%Y-%m-%d"),
                    "Time": rev_time.strftime("%H:%M:%S"),
                }
            )

        except Exception as e:
            print("ROW ERROR:", e)
            continue

    return matches
