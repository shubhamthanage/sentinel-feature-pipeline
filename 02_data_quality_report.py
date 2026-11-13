"""Step 2 - data quality report: nulls, duplicates, wrong types, amount outliers, rows per split."""
import json
import numpy as np
import pandas as pd
import sentinel_lib as L
import config as C

T = L.load_all()
tx, rep = T["transactions"], {}
lines = ["# SENTINEL data quality report\n"]

# 1) row count per split ------------------------------------------------------
split = tx["split"].value_counts().reindex(C.SPLITS)
rep["rows_per_split"] = split.to_dict()
lines += ["## 1. Rows per split (transactions)\n", split.rename("rows").to_frame().to_markdown(), f"\nTotal: **{len(tx):,}**\n"]
lab = T["labels"].groupby("split")["fraud_label"].agg(["count", "sum", "mean"]).reindex(C.SPLITS)
lab.columns = ["labels", "fraud", "fraud_rate"]
lines += ["Labels per split:\n", lab.round(5).to_markdown(), "\n"]

# 2) nulls per column ---------------------------------------------------------
lines.append("## 2. Nulls per column\n")
rep["nulls"] = {}
for name, df in T.items():
    n = df.isna().sum(); n = n[n > 0]
    rep["nulls"][name] = n.to_dict()
    lines.append(f"**{name}** ({len(df):,} rows): " + (", ".join(f"`{c}`={v:,} ({v/len(df):.2%})" for c, v in n.items()) or "no nulls") + "\n")

# 3) duplicates ---------------------------------------------------------------
keys = {"customers": "customer_id", "merchants": "merchant_id", "devices": "device_id",
        "transactions": "transaction_id", "payment_outcomes": "transaction_id",
        "labels": "transaction_id", "features": "transaction_id"}
lines += ["\n## 3. Duplicates\n", "| table | duplicate keys | fully duplicated rows |", "|---|---|---|"]
rep["duplicates"] = {}
for name, df in T.items():
    dk, dr = int(df.duplicated(keys[name]).sum()), int(df.duplicated().sum())
    rep["duplicates"][name] = {"key": dk, "row": dr}
    lines.append(f"| {name} | {dk} | {dr} |")
# business-level duplicate: same customer+merchant+amount+timestamp under different ids
biz = int(tx.duplicated(["customer_id", "merchant_id", "amount_paise", "transaction_time"]).sum())
rep["duplicates"]["transactions_business_key"] = biz
lines.append(f"\nSame customer + merchant + amount + timestamp (different ids): **{biz}**\n")

# 4) wrong types --------------------------------------------------------------
lines.append("\n## 4. Wrong types / invalid values\n")
problems = {}
ts = pd.to_datetime(tx["transaction_time"], utc=True, errors="coerce")
problems["transaction_time not parseable"] = int(ts.isna().sum())
problems["transaction_amount not numeric"] = int(pd.to_numeric(tx["transaction_amount"], errors="coerce").isna().sum() - tx["transaction_amount"].isna().sum())
problems["amount <= 0"] = int((pd.to_numeric(tx["transaction_amount"], errors="coerce") <= 0).sum())
problems["amount_paise != round(amount*100)"] = int((tx["amount_paise"] != (tx["transaction_amount"] * 100).round()).sum())
bad_loc = lambda s: s.notna() & s.map(lambda x: np.isnan(L.parse_loc(x)[1]))
problems["customer_location present but not valid JSON lat/lon"] = int(bad_loc(tx["customer_location"]).sum())
problems["merchant_location present but not valid JSON lat/lon"] = int(bad_loc(tx["merchant_location"]).sum())
cu = T["customers"]
problems["customers.created_at not parseable"] = int(pd.to_datetime(cu["created_at"], utc=True, errors="coerce").isna().sum())
problems["transaction before account creation"] = int((ts < pd.to_datetime(tx.customer_id.map(cu.set_index("customer_id")["created_at"]), utc=True)).sum())
problems["fraud_label not in {0,1}"] = int((~T["labels"]["fraud_label"].isin([0, 1])).sum())
problems["payment status not SUCCESS/FAILED"] = int((~T["payment_outcomes"]["status"].isin(["SUCCESS", "FAILED"])).sum())
rep["type_problems"] = problems
lines += ["| check | rows affected |", "|---|---|"] + [f"| {k} | {v} |" for k, v in problems.items()]
lines.append("\nColumn dtypes (transactions):\n\n```\n" + tx.dtypes.astype(str).to_string() + "\n```\n")

# 5) outliers in amount -------------------------------------------------------
a = tx["transaction_amount"].astype(float)
q1, q3 = a.quantile([.25, .75]); iqr = q3 - q1
log = np.log1p(a); lq1, lq3 = log.quantile([.25, .75]); liqr = lq3 - lq1
mask_iqr = a > q3 + 1.5 * iqr
mask_log = (log > lq3 + 1.5 * liqr) | (log < lq1 - 1.5 * liqr)
rep["amount"] = {"min": a.min(), "median": a.median(), "mean": a.mean(), "p99": a.quantile(.99), "p999": a.quantile(.999), "max": a.max(),
                 "outliers_iqr_raw": int(mask_iqr.sum()), "outliers_iqr_log": int(mask_log.sum())}
fr = tx.merge(T["labels"][["transaction_id", "fraud_label"]], on="transaction_id")
lines += ["\n## 5. Outliers in transaction_amount\n",
          a.describe(percentiles=[.5, .9, .99, .999]).round(2).to_frame("amount").to_markdown(),
          f"\n- Raw IQR rule (> Q3 + 1.5*IQR = {q3 + 1.5*iqr:,.0f}): **{int(mask_iqr.sum()):,}** rows ({mask_iqr.mean():.2%})",
          f"- IQR on log(amount): **{int(mask_log.sum()):,}** rows ({mask_log.mean():.2%})",
          f"- Fraud rate among raw-IQR outliers: {fr.loc[mask_iqr.values, 'fraud_label'].mean():.3%} vs {fr.loc[~mask_iqr.values, 'fraud_label'].mean():.3%} for the rest",
          "\nAmounts are heavy-tailed (not normal), so I report outliers but do **not** delete them: big amounts are real signal for the amount-spike reason code.\n"]

# 6) time ranges per split ----------------------------------------------------
rng = tx.assign(t=ts).groupby("split")["t"].agg(["min", "max"]).reindex(C.SPLITS)
lines += ["\n## 6. Time range per split\n", rng.to_markdown(), "\n"]

(C.OUT_DIR / "data_quality_report.md").write_text("\n".join(lines))
(C.OUT_DIR / "data_quality_report.json").write_text(json.dumps(rep, indent=2, default=str))
print("\n".join(lines))
print(f"\nSaved -> {C.OUT_DIR/'data_quality_report.md'} and .json")
