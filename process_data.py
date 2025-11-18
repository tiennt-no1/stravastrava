import csv
import os
import time
from datetime import datetime, timedelta, timezone
import requests
import sys

# ================== CONFIG ==================

CLIENT_ID = "184098"
CLIENT_SECRET = "5f1a1308dc7f1d471ea540ff9ed925066afe6c2" 

TOKENS_CSV = "tokens.csv"

# --- OUTPUT FILE CONFIG ---
LEADERBOARD_CSV = "leaderboard.csv"
DAILY_KM_CSV = "daily_km.csv"
INVALID_ACTIVITIES_CSV = "invalid_activities.csv"
# --------------------------

# Thời gian tính thành tích (giờ VN, UTC+7)
VN_TZ = timezone(timedelta(hours=7))

# Vùng thời gian phân tích
# START_VN chỉ là MỐC THỜI GIAN SỚM NHẤT mà bạn muốn bắt đầu theo dõi.
START_VN = datetime(2025, 11, 1, 0, 0, 0, tzinfo=VN_TZ)
END_VN  = datetime(2025, 11, 30, 23, 59, 59, tzinfo=VN_TZ) 

# Pace hợp lệ (min/km): 4 < pace < 15
PACE_MIN = 4.0
PACE_MAX = 15.0

# Giới hạn km / ngày
DAILY_CAP_KM = 10.0

# API config
STRAVA_BASE = "https://www.strava.com/api/v3"
PER_PAGE = 100
REQ_SLEEP = 0.15 

# ================== HELPERS ==================

def to_epoch(dt: datetime) -> int:
    """Chuyển datetime sang epoch (timestamp) UTC."""
    return int(dt.astimezone(timezone.utc).timestamp())

GLOBAL_AFTER = to_epoch(START_VN)
GLOBAL_BEFORE = to_epoch(END_VN)


def pace_min_per_km_from_mps(mps: float) -> float:
    """Convert average speed (m/s) -> pace (min/km)."""
    if not mps or mps <= 0:
        return float("inf")
    return (1000.0 / mps) / 60.0


def ensure_fresh_token(row: dict):
    # (Hàm này giữ nguyên)
    access_token = row.get("access_token", "")
    refresh_token = row.get("refresh_token", "")
    expires_at_str = row.get("expires_at", "") or "0"
    try:
        expires_at = int(float(expires_at_str))
    except ValueError:
        expires_at = 0

    now_epoch = int(time.time())

    if refresh_token and now_epoch > (expires_at - 300):
        print(f"  -> Refreshing token for athlete {row.get('athlete_id')}")
        r = requests.post(
            f"{STRAVA_BASE}/oauth/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  !! Refresh failed: {r.status_code} {r.text}")
            return access_token, refresh_token, expires_at, False
        tok = r.json()
        return tok["access_token"], tok["refresh_token"], tok["expires_at"], True

    return access_token, refresh_token, expires_at, False


def get_athlete_activities(token: str, after_ts: int, before_ts: int):
    # (Hàm này giữ nguyên)
    acts = []
    page = 1
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"  -> Querying activities: after={datetime.utcfromtimestamp(after_ts).strftime('%Y-%m-%d %H:%M:%S UTC')}, before={datetime.utcfromtimestamp(before_ts).strftime('%Y-%m-%d %H:%M:%S UTC')}")

    while True:
        params = {"after": after_ts, "before": before_ts,
                  "per_page": PER_PAGE, "page": page}
        r = requests.get(f"{STRAVA_BASE}/athlete/activities",
                         headers=headers, params=params, timeout=30)
        if r.status_code == 429:
            print("  !! Hit rate limit, sleeping 15s...")
            time.sleep(15)
            continue
        r.raise_for_status()
        batch = r.json()
        acts.extend(batch)
        time.sleep(REQ_SLEEP)
        if not batch or len(batch) < PER_PAGE:
            break
        page += 1

    return acts


def get_activity_laps(token: str, activity_id: int):
    # (Hàm này giữ nguyên)
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(
        f"{STRAVA_BASE}/activities/{activity_id}/laps",
        headers=headers,
        timeout=30,
    )
    if r.status_code == 404:
        return []
    if r.status_code == 429:
        print("  !! Hit rate limit on laps, sleeping 15s...")
        time.sleep(15)
        return get_activity_laps(token, activity_id)
    r.raise_for_status()
    time.sleep(REQ_SLEEP)
    return r.json()


def iso_to_vn_date(iso_str: str):
    # (Hàm này giữ nguyên)
    if not iso_str:
        return None
    dt_utc = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    dt_vn = dt_utc.astimezone(VN_TZ)
    return dt_vn.date().isoformat()


def load_tokens(path: str):
    # (Hàm này giữ nguyên)
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            epoch_str = row.get("latest_activity_epoch", "0") or "0"
            try:
                row["latest_activity_epoch"] = int(float(epoch_str))
            except ValueError:
                row["latest_activity_epoch"] = 0
            rows.append(row)
    return rows


def save_tokens(path: str, rows):
    # (Hàm này giữ nguyên)
    if not rows:
        return
    fieldnames = [
        "athlete_id", "firstname", "lastname",
        "access_token", "refresh_token", "expires_at", 
        "scope", "latest_activity_epoch"
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


# ================== MAIN ==================

def gen_report():
    token_rows = load_tokens(TOKENS_CSV)
    if not token_rows:
        raise Exception("⚠️  tokens.csv rỗng hoặc không tồn tại.")

    print(f"Phạm vi phân tích cố định (Giờ VN): {START_VN} -> {END_VN}")

    leaderboard_rows = []
    daily_rows = []
    invalid_rows = []

    updated_token_rows = []

    for row in token_rows:
        athlete_id = row.get("athlete_id", "")
        firstname = row.get("firstname", "")
        lastname = row.get("lastname", "")
        latest_epoch_csv = row.get("latest_activity_epoch", 0)

        print(f"\n=== Athlete {firstname} {lastname} (ID {athlete_id}) ===")
        print(f"  * Latest processed epoch (CSV): {latest_epoch_csv}")

        access_token, refresh_token, expires_at, refreshed = ensure_fresh_token(row)
        
        row["access_token"] = access_token
        row["refresh_token"] = refresh_token
        row["expires_at"] = str(expires_at)
        
        # Logic tính toán after mới
        query_after_csv = latest_epoch_csv + 1 if latest_epoch_csv > 0 else 0
        query_after_ts = max(GLOBAL_AFTER, query_after_csv)
        query_before_ts = GLOBAL_BEFORE
        
        if query_after_ts >= query_before_ts:
             print("  -> Mốc thời gian truy vấn đã vượt quá END_VN hoặc không có hoạt động mới trong phạm vi.")
             updated_token_rows.append(row)
             continue
        
        if not access_token:
            print("  !! Không có access_token, bỏ qua.")
            updated_token_rows.append(row)
            continue

        try:
            activities = get_athlete_activities(access_token, query_after_ts, query_before_ts)
            print(f"  -> Đã tìm thấy {len(activities)} hoạt động mới/cập nhật.")
        except Exception as e:
            print(f"  !! Lỗi fetch activities: {e}")
            updated_token_rows.append(row)
            continue
            
        new_latest_epoch = latest_epoch_csv
        if activities:
            max_epoch_fetched = max(to_epoch(datetime.fromisoformat(act.get("start_date").replace("Z", "+00:00"))) for act in activities)
            new_latest_epoch = max(latest_epoch_csv, max_epoch_fetched)

        row["latest_activity_epoch"] = new_latest_epoch
        updated_token_rows.append(row)
        print(f"  * Latest processed epoch (NEW): {new_latest_epoch}")


        # Tổng kết theo ngày (raw & capped) - (Phần này giữ nguyên logic tính toán)
        daily_raw = {} 
        daily_valid_act_count = {} 
        total_raw_km = 0.0
        total_capped_km = 0.0
        total_runs_count = 0

        for act in activities:
            act_type = act.get("type")
            if act_type not in ("Run", "TrailRun"):
                continue

            act_id = act.get("id")
            name = act.get("name")
            start_date = act.get("start_date") 
            day_vn = iso_to_vn_date(start_date)
            distance_m = act.get("distance", 0.0) or 0.0
            dist_km = distance_m / 1000.0

            try:
                laps = get_activity_laps(access_token, act_id)
            except Exception as e:
                print(f"  !! Lỗi fetch laps cho activity {act_id}: {e}")
                laps = []

            lap_paces = []
            for lap in laps:
                avg_speed = lap.get("average_speed") 
                if avg_speed is not None:
                    lap_paces.append(pace_min_per_km_from_mps(avg_speed))

            invalid = False
            if not lap_paces:
                invalid = True
            else:
                for p in lap_paces:
                    if p <= PACE_MIN or p >= PACE_MAX:
                        invalid = True
                        break

            if invalid:
                invalid_rows.append({
                    "athlete_id": athlete_id, "firstname": firstname, "lastname": lastname,
                    "activity_id": act_id, "name": name, "type": act_type, "start_date": start_date,
                    "distance_km": round(dist_km, 2),
                    "avg_lap_pace_min_per_km_list": ", ".join(f"{p:.2f}" for p in lap_paces) if lap_paces else "NO_LAPS",
                    "activity_url": f"https://www.strava.com/activities/{act_id}",
                    "map_summary_polyline": (act.get("map") or {}).get("summary_polyline", ""),
                })
                continue

            total_runs_count += 1
            total_raw_km += dist_km

            if day_vn:
                daily_raw[day_vn] = daily_raw.get(day_vn, 0.0) + dist_km
                daily_valid_act_count[day_vn] = daily_valid_act_count.get(day_vn, 0) + 1

        for day, raw_km in sorted(daily_raw.items()):
            capped_km = raw_km if raw_km <= DAILY_CAP_KM else DAILY_CAP_KM
            total_capped_km += capped_km

            daily_rows.append({
                "athlete_id": athlete_id, "firstname": firstname, "lastname": lastname,
                "date_vn": day, "raw_distance_km": round(raw_km, 2), "capped_distance_km": round(capped_km, 2),
                "valid_activities_count": daily_valid_act_count.get(day, 0),
            })

        leaderboard_rows.append({
            "athlete_id": athlete_id, "firstname": firstname, "lastname": lastname,
            "total_raw_distance_km": round(total_raw_km, 2), "total_capped_distance_km": round(total_capped_km, 2),
            "valid_runs_count": total_runs_count,
        })

    # Lưu lại tokens (sau khi refresh và cập nhật latest_activity_epoch)
    save_tokens(TOKENS_CSV, updated_token_rows)

    # Xuất CSV leaderboard (Sử dụng hằng số mới)
    if leaderboard_rows:
        leaderboard_rows.sort(
            key=lambda r: (r["total_capped_distance_km"], r["valid_runs_count"]),
            reverse=True,
        )
        fieldnames = [
            "athlete_id", "firstname", "lastname",
            "total_raw_distance_km", "total_capped_distance_km",
            "valid_runs_count",
        ]
        with open(LEADERBOARD_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in leaderboard_rows:
                writer.writerow(r)

    # Xuất CSV daily_km (Sử dụng hằng số mới)
    if daily_rows:
        daily_rows.sort(key=lambda r: (r["date_vn"], r["athlete_id"]))
        fieldnames = [
            "athlete_id", "firstname", "lastname",
            "date_vn", "raw_distance_km", "capped_distance_km",
            "valid_activities_count",
        ]
        with open(DAILY_KM_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in daily_rows:
                writer.writerow(r)

    # Xuất CSV invalid_activities (Sử dụng hằng số mới)
    if invalid_rows:
        fieldnames = [
            "athlete_id", "firstname", "lastname",
            "activity_id", "name", "type", "start_date",
            "distance_km", "avg_lap_pace_min_per_km_list",
            "activity_url", "map_summary_polyline",
        ]
        with open(INVALID_ACTIVITIES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in invalid_rows:
                writer.writerow(r)

    print("\n✅ Done.")
    print(f"- {TOKENS_CSV} đã được cập nhật mốc thời gian đã xử lý mới nhất.")
    print(f"- {LEADERBOARD_CSV}           → tổng km (raw & capped) mỗi athlete")
    print(f"- {DAILY_KM_CSV}              → km từng ngày (raw & capped, giờ VN)")
    print(f"- {INVALID_ACTIVITIES_CSV}    → các activity bị loại do pace ngoài ({PACE_MIN}, {PACE_MAX})")

# if __name__ == "__main__":
#     main()