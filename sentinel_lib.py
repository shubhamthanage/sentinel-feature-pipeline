"""Shared helpers: loading, feature maths, reason codes. Scripts 01-05 import from here."""
import glob, json
import numpy as np
import pandas as pd
import config as C


# ---------------------------------------------------------------- loading
def load_table(name: str) -> pd.DataFrame:
    files = sorted(glob.glob(str(C.DATA_DIR / name / "*" / "*.csv.gz")))
    if not files:
        raise FileNotFoundError(f"No files for '{name}' under {C.DATA_DIR}. Check DATA_DIR in .env")
    return pd.concat((pd.read_csv(f) for f in files), ignore_index=True)


def load_all() -> dict:
    return {t: load_table(t) for t in C.TABLES}


def parse_loc(s):
    """'{"city":"Pune","lat":18.5,"lon":73.8}' -> (city, lat, lon); (None, nan, nan) if missing/bad."""
    try:
        j = json.loads(s)
        return j.get("city"), float(j["lat"]), float(j["lon"])
    except Exception:
        return None, np.nan, np.nan


# ---------------------------------------------------------------- maths
def haversine_km(lat1, lon1, lat2, lon2, R=C.EARTH_RADIUS_KM):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def _prior_window(series_by_time, window):
    """Rolling window that EXCLUDES the current row (closed='left') -> no leakage."""
    return series_by_time.rolling(window, closed="left")


def _prev_time_strict(keys: pd.DataFrame, t: pd.Series) -> pd.Series:
    """Latest earlier time in the same group, using ONLY times strictly before t.
    A plain groupby().shift(1) would treat another row at the SAME timestamp as history
    (leakage), so ties are collapsed to one time before shifting."""
    cols = list(keys.columns)
    k = keys.assign(t=t)
    uniq = k.drop_duplicates(cols + ["t"]).sort_values(cols + ["t"])
    uniq["prev_t"] = uniq.groupby(cols)["t"].shift(1)
    return k.merge(uniq, on=cols + ["t"], how="left")["prev_t"].set_axis(keys.index)


# ---------------------------------------------------------------- features
def build_base(tables: dict) -> pd.DataFrame:
    """Transactions + outcome, sorted per customer by time (this order is what makes rolling safe)."""
    tx = tables["transactions"].copy()
    po = tables["payment_outcomes"][["transaction_id", "outcome_time", "status"]]
    df = tx.merge(po, on="transaction_id", how="left")
    df["t"] = pd.to_datetime(df["transaction_time"], utc=True)
    df["outcome_t"] = pd.to_datetime(df["outcome_time"], utc=True)
    return df.sort_values(["customer_id", "t", "transaction_id"]).reset_index(drop=True)


def compute_features(df: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    out = df[["transaction_id", "customer_id", "split", "merchant_category"]].copy()
    ratio = np.full(len(df), np.nan)
    cnt1h = np.zeros(len(df))
    amt24 = np.zeros(len(df))
    fails = np.zeros(len(df), dtype=int)

    # rolling windows per customer (history includes warmup + declines)
    for _, g in df.groupby("customer_id", sort=False):
        idx = g.index.values
        s = g.set_index("t")
        amt = s["transaction_amount"]
        r = _prior_window(amt, C.AVG_WINDOW)
        mean90 = (r.sum() / r.count()).values            # NaN when no history
        ratio[idx] = g["transaction_amount"].values / mean90
        cnt1h[idx] = _prior_window(pd.Series(1.0, index=s.index), C.VELOCITY_WINDOW).sum().fillna(0).values
        amt24[idx] = _prior_window(s["amount_paise"].astype(float), C.AMOUNT_WINDOW).sum().fillna(0).values
        # failures: only FAILED outcomes already RECEIVED (outcome_time <= now) in the last 24h
        fo = np.sort(g.loc[g["status"] == "FAILED", "outcome_t"].values)
        t = g["t"].values
        lo = np.searchsorted(fo, t - np.timedelta64(24, "h"), side="right")
        hi = np.searchsorted(fo, t, side="right")
        fails[idx] = hi - lo
    out["amount_to_average_ratio"] = ratio
    out["transaction_count_last_1_hour"] = cnt1h.astype(int)
    out["transaction_amount_last_24_hours_paise"] = amt24.astype(np.int64)
    out["failed_transactions_24h"] = fails
    out["has_recent_failures"] = fails >= C.FAILED_ATTEMPTS_MIN

    # is_new_device: previous time (strictly earlier) THIS customer used THIS device
    has_dev = df["device_id"].notna()
    prev = _prev_time_strict(df.loc[has_dev, ["customer_id", "device_id"]], df.loc[has_dev, "t"])
    gap = df.loc[has_dev, "t"] - prev
    nd = pd.Series(pd.NA, index=df.index, dtype="object")
    nd[has_dev] = (prev.isna() | (gap > pd.Timedelta(C.DEVICE_WINDOW))).astype(bool)
    out["is_new_device"] = nd

    # distance + is_new_city (merchant city never seen for the customer in 90 days)
    cl = df["customer_location"].map(parse_loc)
    ml = df["merchant_location"].map(parse_loc)
    clat = np.array([x[1] for x in cl]); clon = np.array([x[2] for x in cl])
    mlat = np.array([x[1] for x in ml]); mlon = np.array([x[2] for x in ml])
    out["customer_merchant_distance_km"] = haversine_km(clat, clon, mlat, mlon).round(2)
    ccity = pd.Series([x[0] for x in cl], index=df.index)
    known = ccity.notna()
    prevc = _prev_time_strict(df.loc[known, ["customer_id"]].assign(c=ccity[known]), df.loc[known, "t"])
    gapc = df.loc[known, "t"] - prevc
    nc = pd.Series(pd.NA, index=df.index, dtype="object")
    nc[known] = (prevc.isna() | (gapc > pd.Timedelta("90D"))).astype(bool)
    out["is_new_city"] = nc

    # time of day in IST
    ist = df["t"].dt.tz_convert(C.IST)
    out["hour_of_day"] = ist.dt.hour
    out["is_night"] = (ist.dt.hour >= C.NIGHT_START_HOUR) & (ist.dt.hour < C.NIGHT_END_HOUR)

    # account age (whole days)
    created = pd.to_datetime(df["customer_id"].map(customers.set_index("customer_id")["created_at"]), utc=True)
    out["account_age"] = (df["t"] - created).dt.days
    out["is_new_account"] = out["account_age"] < C.NEW_ACCOUNT_DAYS
    return out


# ---------------------------------------------------------------- reason codes
def _b(x):
    return x.map({True: True, False: False}).fillna(False).astype(bool)


def assign_reason_codes(f: pd.DataFrame) -> pd.DataFrame:
    r = pd.DataFrame(index=f.index)
    r["R01_NEW_DEVICE"] = _b(f["is_new_device"])
    r["R02_GEO_MISMATCH"] = _b(f["is_new_city"]) | (f["customer_merchant_distance_km"] > C.GEO_DISTANCE_KM)
    r["R03_ODD_HOUR"] = f["is_night"].astype(bool)
    r["R04_FAILED_ATTEMPTS"] = f["has_recent_failures"].astype(bool)
    r["R05_AMOUNT_SPIKE"] = (f["amount_to_average_ratio"] > C.AMOUNT_SPIKE_RATIO).fillna(False)
    r["R06_NEW_ACCOUNT"] = f["is_new_account"].astype(bool)
    r["R07_VELOCITY"] = f["transaction_count_last_1_hour"] >= C.VELOCITY_COUNT_MIN
    r["R08_HIGH_RISK_MCC"] = f["merchant_category"].isin(C.HIGH_RISK_MCC)
    return r[C.REASON_CODES]


def codes_as_list(r: pd.DataFrame):
    return r.apply(lambda row: [c for c in C.REASON_CODES if row[c]], axis=1)
