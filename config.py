"""Settings + the class thresholds. Every number used by the pipeline lives here."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
# where the tables come from: "supabase" (REST API, the default) or "csv" (local gzipped export)
DATA_SOURCE = os.getenv("DATA_SOURCE", "supabase").strip().lower()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")      # publishable / anon key, read-only is enough
API_PAGE_SIZE = 1000                          # Supabase returns at most 1,000 rows per request
API_WORKERS = 8                               # parallel page requests
DATA_DIR = Path(os.getenv("DATA_DIR", "../supabase_db_kit/data/tables")).expanduser()
OUT_DIR = Path(__file__).parent / "output"
OUT_DIR.mkdir(exist_ok=True)

SPLITS = ["warmup", "train", "validation", "holdout"]
TABLES = ["customers", "merchants", "devices", "transactions", "payment_outcomes", "labels", "features"]
PRIMARY_KEYS = {"customers": "customer_id", "merchants": "merchant_id", "devices": "device_id",
                "transactions": "transaction_id", "payment_outcomes": "transaction_id",
                "labels": "transaction_id", "features": "transaction_id"}
JSON_COLUMNS = {"merchants": ["merchant_location"], "transactions": ["customer_location", "merchant_location"],
                "features": ["reason_codes"]}
TIMESTAMP_COLUMNS = {"customers": ["created_at"], "transactions": ["transaction_time"],
                     "payment_outcomes": ["outcome_time"], "labels": ["label_available_at"],
                     "features": ["feature_as_of", "mcc_encoding_as_of"]}

# ---- feature windows --------------------------------------------------------
AVG_WINDOW = "90D"          # amount_to_average_ratio: customer's 90-day average
DEVICE_WINDOW = "90D"       # is_new_device: device not seen for the customer in 90 days
VELOCITY_WINDOW = "1h"      # transaction_count_last_1_hour
AMOUNT_WINDOW = "24h"       # transaction_amount_last_24_hours
FAIL_WINDOW = "24h"         # failed outcomes window
EARTH_RADIUS_KM = 6371.0    # haversine
NIGHT_START_HOUR, NIGHT_END_HOUR = 0, 5   # IST, 00:00 inclusive -> 05:00 exclusive
IST = "Asia/Kolkata"

# ---- reason-code thresholds (from class / client rules) ---------------------
FAILED_ATTEMPTS_MIN = 3          # R04: >= 3 failed outcomes in last 24h
NEW_ACCOUNT_DAYS = 30            # R06: account younger than 30 days
GEO_DISTANCE_KM = 500            # R02: distance above 500 km (or a new city)
AMOUNT_SPIKE_RATIO = 5.0         # R05: amount more than 5x customer's 90-day average
VELOCITY_COUNT_MIN = 4           # R07: 4 or more attempts in the last hour
HIGH_RISK_MCC = {"electronics", "gaming", "gift_cards"}   # R08

REASON_CODES = ["R01_NEW_DEVICE", "R02_GEO_MISMATCH", "R03_ODD_HOUR", "R04_FAILED_ATTEMPTS",
                "R05_AMOUNT_SPIKE", "R06_NEW_ACCOUNT", "R07_VELOCITY", "R08_HIGH_RISK_MCC"]
