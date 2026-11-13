"""Step 4 - assign reason codes R01-R08 (velocity + high-risk MCC included) and sanity-check them against fraud labels."""
import pandas as pd
import sentinel_lib as L
import config as C

T = L.load_all()
df = L.build_base(T)
f = L.compute_features(df, T["customers"])
r = L.assign_reason_codes(f)
f["reason_codes"] = L.codes_as_list(r).map(lambda x: str(x).replace("'", '"').replace(", ", ","))
f = pd.concat([f, r], axis=1)

print("Thresholds used (config.py):")
print(f"  R02 distance > {C.GEO_DISTANCE_KM} km or new city | R04 failures >= {C.FAILED_ATTEMPTS_MIN} in 24h | R05 ratio > {C.AMOUNT_SPIKE_RATIO}")
print(f"  R06 account < {C.NEW_ACCOUNT_DAYS} days | R07 >= {C.VELOCITY_COUNT_MIN} attempts in 1h | R08 MCC in {sorted(C.HIGH_RISK_MCC)}\n")

lab = T["labels"].set_index("transaction_id")["fraud_label"]
f["fraud_label"] = f["transaction_id"].map(lab)
base = f["fraud_label"].mean()
rows = [{"code": c, "fired": int(f[c].sum()), "fired_%": round(f[c].mean() * 100, 2),
         "fraud_rate_when_fired_%": round(f.loc[f[c], "fraud_label"].mean() * 100, 3),
         "lift_vs_base": round(f.loc[f[c], "fraud_label"].mean() / base, 1) if f[c].any() else None} for c in C.REASON_CODES]
tab = pd.DataFrame(rows)
print(tab.to_string(index=False))
print(f"\nBase fraud rate: {base*100:.3f}%   |  transactions with no code: {(f[C.REASON_CODES].sum(axis=1)==0).mean()*100:.1f}%")

# why these three MCCs are 'high risk' - evidence from the TRAIN labels only (no peeking at holdout)
tr = f[f.split == "train"].groupby("merchant_category")["fraud_label"].agg(["count", "mean"]).sort_values("mean", ascending=False)
tr["high_risk_in_config"] = tr.index.isin(C.HIGH_RISK_MCC)
print("\nFraud rate per merchant category (train split):")
print(tr.round(4).to_string())

f.drop(columns=["fraud_label"]).to_csv(C.OUT_DIR / "reason_codes.csv", index=False)
tab.to_csv(C.OUT_DIR / "reason_code_summary.csv", index=False)
print(f"\nSaved -> {C.OUT_DIR/'reason_codes.csv'}")
