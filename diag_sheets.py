"""Standalone diagnostic for the Google Sheets connection. Run with:
    python diag_sheets.py
Reads .streamlit/secrets.toml directly (no Streamlit needed)."""
import sys
import tomllib
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SECRETS = Path(__file__).parent / ".streamlit" / "secrets.toml"

with open(SECRETS, "rb") as f:
    cfg = tomllib.load(f)

sheet_id = cfg.get("gsheet_id", "")
sa = cfg.get("gcp_service_account", {})

print(f"gsheet_id          = {sheet_id!r}")
print(f"client_email       = {sa.get('client_email')!r}")
print(f"private_key starts = {sa.get('private_key', '')[:40]!r}")
print(f"private_key length = {len(sa.get('private_key', ''))}")
print()

if not sheet_id or sheet_id.startswith("PASTE_"):
    print("ERROR: gsheet_id is missing or still the placeholder.")
    sys.exit(1)

try:
    creds = Credentials.from_service_account_info(
        sa,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    print("OK: credentials parsed")
    client = gspread.authorize(creds)
    print("OK: client authorised")
    sheet = client.open_by_key(sheet_id)
    print(f"OK: opened spreadsheet {sheet.title!r}")
    print(f"     existing worksheets: {[ws.title for ws in sheet.worksheets()]}")
    ws = sheet.sheet1
    ws.append_row(["diag_test_row", "hello", "from python"])
    print("OK: appended a test row to first worksheet")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
    sys.exit(1)
