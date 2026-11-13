"""Step 1 - load the six SENTINEL tables (+ the provided features table) from Supabase into pandas and sanity-check them."""
import sentinel_lib as L
import config as C

tables = L.load_all()
src = f"Supabase REST API ({C.SUPABASE_URL})" if C.DATA_SOURCE == "supabase" else f"CSV export ({C.DATA_DIR})"
print(f"DATA_SOURCE = {C.DATA_SOURCE}  ->  loaded from {src}\n")
for name, df in tables.items():
    print(f"=== {name}: {len(df):,} rows x {df.shape[1]} columns")
    print(df.head(2).T.head(8).to_string(), "\n")

# foreign-key sanity: every transaction must point at a known customer / merchant / outcome / label
tx = tables["transactions"]
checks = {
    "tx.customer_id in customers": tx.customer_id.isin(tables["customers"].customer_id).mean(),
    "tx.merchant_id in merchants": tx.merchant_id.isin(tables["merchants"].merchant_id).mean(),
    "tx.device_id in devices (non-null)": tx.device_id.dropna().isin(tables["devices"].device_id).mean(),
    "tx has a payment_outcome": tx.transaction_id.isin(tables["payment_outcomes"].transaction_id).mean(),
    "tx has a label": tx.transaction_id.isin(tables["labels"].transaction_id).mean(),
    "tx has a provided feature row": tx.transaction_id.isin(tables["features"].transaction_id).mean(),
}
print("=== Join integrity (1.0 = every row joins)")
for k, v in checks.items():
    print(f"  {k:40s} {v:.4f}")
