#!/usr/bin/env python3
"""
Google Sheets → Twilio Toll-Free SMS blaster (500/day cap)
"""

import os
import sys
import time
import datetime as dt
from typing import List, Tuple

from dotenv import load_dotenv
load_dotenv()

import gspread
from google.oauth2.service_account import Credentials
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

# ---------- Config ----------
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "500"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

SHEET_ID = os.getenv("GSPREAD_SHEET_ID")
WORKSHEET = os.getenv("GSPREAD_WORKSHEET", "Sheet1")
SA_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")

# Basic validation
missing = [k for k,v in [
    ("GSPREAD_SHEET_ID", SHEET_ID),
    ("GOOGLE_SERVICE_ACCOUNT_JSON", SA_PATH),
    ("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT_SID),
    ("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN),
    ("TWILIO_FROM", TWILIO_FROM),
] if not v]
if missing:
    print(f"[CONFIG] Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)

# ---------- Helpers ----------
def get_gspread_client() -> gspread.Client:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly"
    ]
    creds = Credentials.from_service_account_file(SA_PATH, scopes=scopes)
    return gspread.authorize(creds)

def open_worksheet(gc: gspread.Client):
    sh = gc.open_by_key(SHEET_ID)
    return sh.worksheet(WORKSHEET)

def find_header_indexes(header_row: List[str]):
    # Normalize headers
    header_map = {h.strip().lower(): idx for idx, h in enumerate(header_row)}
    def idx_for(name: str, default=None):
        return header_map.get(name.lower(), default)
    idx_number = idx_for("number")
    idx_message = idx_for("message")
    idx_status  = idx_for("status", None)
    idx_sent_at = idx_for("sent_at", None)
    idx_sid     = idx_for("sid", None)
    idx_error   = idx_for("error", None)
    if idx_number is None or idx_message is None:
        raise RuntimeError("Headers must include at least 'Number' and 'Message'.")
    return idx_number, idx_message, idx_status, idx_sent_at, idx_sid, idx_error

def now_iso():
    return dt.datetime.now().isoformat(timespec="seconds")

def rows_to_send(values: List[List[str]], idx_status: int) -> List[Tuple[int, List[str]]]:
    """
    Returns a list of (1-based row_number, row_values) to send, skipping already SENT rows.
    Assumes row 1 is the header.
    """
    targets = []
    for i, row in enumerate(values[1:], start=2):
        status = (row[idx_status] if idx_status is not None and idx_status < len(row) else "").strip().upper()
        if status == "SENT":
            continue
        if not any((cell or "").strip() for cell in row):
            continue
        targets.append((i, row))
    return targets

def safe_get(row: List[str], idx: int) -> str:
    return (row[idx] if idx is not None and idx < len(row) else "").strip()

def mask(e164: str) -> str:
    """Mask number for console logs: +1416***1234."""
    if not e164 or len(e164) < 6: 
        return e164
    return e164[:6] + "***" + e164[-4:]

# ---------- Main ----------
def main():
    print(f"[START] DRY_RUN={DRY_RUN} DAILY_LIMIT={DAILY_LIMIT}")
    print(f"[SHEET] opening id={SHEET_ID} tab={WORKSHEET}")
    gc = get_gspread_client()
    ws = open_worksheet(gc)

    # Read all data
    values = ws.get_all_values()
    if not values:
        print("[INFO] Sheet is empty.")
        return 0

    idx_number, idx_message, idx_status, idx_sent_at, idx_sid, idx_error = find_header_indexes(values[0])

    # If Status column missing, create it (and others) so we can update
    header = values[0]
    needs_update = False
    def ensure_col(name: str):
        nonlocal header, needs_update
        if name not in header:
            header.append(name)
            needs_update = True

    ensure_col("Status")
    ensure_col("Sent_At")
    ensure_col("SID")
    ensure_col("Error")

    if needs_update:
        print("[MIGRATE] Adding missing tracking columns (Status/Sent_At/SID/Error)")
        ws.update('A1', [header])  # overwrite header row with new columns

    # Recompute indexes after potential header change
    idx_number, idx_message, idx_status, idx_sent_at, idx_sid, idx_error = find_header_indexes(ws.row_values(1))

    all_values = ws.get_all_values()
    targets = rows_to_send(all_values, idx_status)
    if not targets:
        print("[INFO] Nothing to send. All rows are SENT or empty.")
        return 0

    to_send = targets[:DAILY_LIMIT]
    print(f"[QUEUE] Pending={len(targets)} | Sending now={len(to_send)} | Skipping later={max(0, len(targets)-len(to_send))}")

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    # Prepare batch updates
    updates = []

    # Determine the columns (1-based) for the fields we update
    col_status = idx_status + 1 if idx_status is not None else len(header)
    col_sent_at = idx_sent_at + 1 if idx_sent_at is not None else len(header)
    col_sid = idx_sid + 1 if idx_sid is not None else len(header)
    col_error = idx_error + 1 if idx_error is not None else len(header)

    sent_ok = 0
    sent_fail = 0
    sent_dry = 0
    skipped_blank = 0

    for row_number, row in to_send:
        number = safe_get(row, idx_number)
        message = safe_get(row, idx_message)

        preview = (message or "")[:80].replace("\n", " ")
        if not number or not message:
            print(f"[SKIP] row={row_number} reason=Missing Number/Message")
            skipped_blank += 1
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_number, col_status) + ":" + gspread.utils.rowcol_to_a1(row_number, col_error),
                "values": [["FAILED", now_iso(), "", "Missing Number or Message"]],
            })
            continue

        if DRY_RUN:
            print(f"[DRY->SEND] row={row_number} to={mask(number)} text='{preview}'")
            sent_dry += 1
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_number, col_status) + ":" + gspread.utils.rowcol_to_a1(row_number, col_error),
                "values": [["SENT", now_iso(), "DRYRUN", ""]],
            })
            continue

        # Append the pitch message to the original message
        full_message = message + "\n\nI recently just finished an AI phone agent that turns incoming calls into booked appointments automatically.\n\nI'm looking to set up a few businesses for essentially free while I set up testimonials.\n\nWould you be open to hearing more? I can also send you a demo call with a phone agent."
        
        print(f"[SEND] row={row_number} to={mask(number)} text='{preview}'")
        # Send SMS with simple retry/backoff
        sid = ""
        error = ""
        for attempt in range(3):
            try:
                msg = client.messages.create(
                    to=number,
                    from_=TWILIO_FROM,
                    body=full_message
                )
                sid = msg.sid
                break
            except TwilioException as e:
                error = str(e)
                sleep_s = 2 ** attempt
                print(f"[WARN] row={row_number} to={mask(number)} attempt={attempt+1}/3 error={error} backoff={sleep_s}s", file=sys.stderr)
                time.sleep(sleep_s)

        if sid:
            print(f"[OK]   row={row_number} to={mask(number)} sid={sid}")
            sent_ok += 1
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_number, col_status) + ":" + gspread.utils.rowcol_to_a1(row_number, col_error),
                "values": [["SENT", now_iso(), sid, ""]],
            })
        else:
            print(f"[FAIL] row={row_number} to={mask(number)} error={error[:200]}")
            sent_fail += 1
            updates.append({
                "range": gspread.utils.rowcol_to_a1(row_number, col_status) + ":" + gspread.utils.rowcol_to_a1(row_number, col_error),
                "values": [["FAILED", now_iso(), "", error[:500]]],
            })

        time.sleep(0.2)  # gentle pacing

    # Batch update in chunks (Sheets API has size limits)
    def chunk(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    for group in chunk(updates, 100):
        ws.batch_update(group)

    print(f"[DONE] Summary → sent_ok={sent_ok} sent_fail={sent_fail} dry_marked={sent_dry} skipped_blank={skipped_blank}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
