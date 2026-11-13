"""Step 3 - compute the six SENTINEL features with ONLY data from before each transaction."""
import random
import numpy as np
import pandas as pd
import sentinel_lib as L
import config as C

T = L.load_all()
df = L.build_base(T)
f = L.compute_features(df, T["customers"])
cols = ["transaction_id", "customer_id", "split", "amount_to_average_ratio", "is_new_device",
        "customer_merchant_distance_km", "is_night", "transaction_count_last_1_hour",
        "transaction_amount_last_24_hours_paise"]
print(f"Computed features for {len(f):,} transactions\n")
print(f[cols].describe(include="all").T.iloc[:, :8].to_string(), "\n")
print("Null counts (nulls are honest 'unknown', never filled with 0):")
print(f[cols[3:]].isna().sum().to_string(), "\n")

# ---- NO-LEAKAGE PROOF: recompute 300 random transactions the slow, obvious way -------------
# for each one, look ONLY at rows with a strictly earlier timestamp for that customer.
random.seed(7)
sample = random.sample(range(len(df)), 300)
bad = 0
for i in sample:
    row = df.loc[i]
    prior = df[(df.customer_id == row.customer_id) & (df.t < row.t)]          # strictly before
    p90 = prior[prior.t >= row.t - pd.Timedelta(C.AVG_WINDOW)]
    exp_ratio = row.transaction_amount / p90.transaction_amount.mean() if len(p90) else np.nan
    exp_c1 = int((prior.t >= row.t - pd.Timedelta(C.VELOCITY_WINDOW)).sum())
    exp_a24 = int(prior[prior.t >= row.t - pd.Timedelta(C.AMOUNT_WINDOW)].amount_paise.sum())
    exp_nd = (pd.NA if pd.isna(row.device_id) else
              not ((prior.device_id == row.device_id) & (prior.t >= row.t - pd.Timedelta(C.DEVICE_WINDOW))).any())
    got = f.loc[i]
    same_ratio = (np.isnan(exp_ratio) and np.isnan(got.amount_to_average_ratio)) or abs(exp_ratio - got.amount_to_average_ratio) < 1e-9
    same_nd = (pd.isna(exp_nd) and pd.isna(got.is_new_device)) or exp_nd == got.is_new_device
    if not (same_ratio and same_nd and exp_c1 == got.transaction_count_last_1_hour
            and exp_a24 == got.transaction_amount_last_24_hours_paise):
        bad += 1
print(f"Leakage check: {300 - bad}/300 random rows identical to a brute-force 'only earlier rows' recomputation")
assert bad == 0, "leakage / window bug found"

# ---- SAME-TIMESTAMP CHECK: two transactions on one device at the exact same instant -------
# neither may count the other as prior history, so both must be is_new_device = True.
tie = df.iloc[[0, 0]].copy().reset_index(drop=True)
tie["transaction_id"] = ["tie_a", "tie_b"]
tie["device_id"] = "tie_device"
tf = L.compute_features(tie, T["customers"])
print(f"Same-timestamp check: is_new_device = {tf.is_new_device.tolist()} (expected [True, True])")
assert tf.is_new_device.tolist() == [True, True], "same-timestamp row leaked into device history"

f.to_csv(C.OUT_DIR / "features_computed.csv", index=False)
print(f"Saved -> {C.OUT_DIR/'features_computed.csv'}")
