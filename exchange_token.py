import requests
import csv
import re
import os

# code_path = '/content/user_code.txt'
# ========== CONFIG ==========
CLIENT_ID = "184098"  # Client ID của bạn
CLIENT_SECRET = "5f1a1308dc7f1d471ea540ff90ed925066afe6c2"  # lấy trong trang https://www.strava.com/settings/api
TOKENS_CSV = "tokens.csv" #Output file chứa access_code, refresh code

# Cách 1: Dán raw text vào đây
# RAW_TEXT = """
# Code: f9abc18b934bf0c3fb23ed128830e8918be624d9
# Scope: read,activity:read_all
# ---
# Code: f9abc18b934bf0c3fb23ed128830e8918be624d9
# Scope: read,activity:read_all
# ---
# Code: c217f383c39af408b32047fcf1ef344c527037ee
# Scope: read,activity:read_all
# ---
# """

# # Đọc từ file codes.txt thì:
# with open(code_path, "r", encoding="utf-8") as f:
#     RAW_TEXT = f.read()




# def extract_codes(raw_text: str):
#     """
#     Tìm tất cả 'Code: xxx' và trả về list các code duy nhất.
#     """
#     codes = re.findall(r"Code:\s*([0-9a-fA-F]+)", raw_text)
#     unique_codes = list(dict.fromkeys(codes))  # giữ thứ tự, bỏ trùng
#     return unique_codes


def exchange_code_for_token(code: str):
    """
    Gọi Strava API đổi authorization code -> access_token, refresh_token, athlete info.
    """
    url = "https://www.strava.com/oauth/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    r = requests.post(url, data=data, timeout=30)
    if r.status_code != 200:
        print(f"❌ Failed to exchange code {code}: {r.status_code} {r.text}")
        return None
    return r.json()


def append_token_row(row, path=TOKENS_CSV):
    """
    Ghi 1 dòng vào tokens.csv. Nếu file chưa tồn tại thì tạo header.
    """
    header = [
        "athlete_id",
        "firstname",
        "lastname",
        "access_token",
        "refresh_token",
        "expires_at",
        "scope",
    ]
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def register_athlete(code):

    print(f"\n🔄 Exchanging code: {code}")
    tok = exchange_code_for_token(code)
    if tok is None:
        raise f"cannot exchange code {code} for token"

    access_token = tok.get("access_token")
    refresh_token = tok.get("refresh_token")
    expires_at = tok.get("expires_at")
    scope = ",".join(tok.get("scope", [])) if isinstance(tok.get("scope"), list) else tok.get("scope", "")
    athlete = tok.get("athlete", {})

    athlete_id = athlete.get("id")
    firstname = athlete.get("firstname", "")
    lastname = athlete.get("lastname", "")

    print(f"✅ Athlete {firstname} {lastname} (ID {athlete_id})")
    print(f"   access_token: {access_token[:8]}... (truncated)")
    print(f"   refresh_token: {refresh_token[:8]}... (truncated)")

    athlete_row = {
            "athlete_id": athlete_id,
            "firstname": firstname,
            "lastname": lastname,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "scope": scope,
        }
    append_token_row(athlete_row)
    return athlete_row
