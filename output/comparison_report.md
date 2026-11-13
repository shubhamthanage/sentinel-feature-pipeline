# Comparison with the provided features table

Rows compared: **110,000** (all four splits)

## Feature match rate

| feature                                | provided_column               |   rows |   matches |   match_rate_% |   null_disagreements |   mismatches |
|:---------------------------------------|:------------------------------|-------:|----------:|---------------:|---------------------:|-------------:|
| amount_to_average_ratio                | amount_to_avg_ratio           | 110000 |    110000 |            100 |                    0 |            0 |
| is_new_device                          | is_new_device                 | 110000 |    110000 |            100 |                    0 |            0 |
| customer_merchant_distance_km          | customer_merchant_distance_km | 110000 |    110000 |            100 |                    0 |            0 |
| is_night                               | is_night                      | 110000 |    110000 |            100 |                    0 |            0 |
| transaction_count_last_1_hour          | txn_count_last_1h             | 110000 |    110000 |            100 |                    0 |            0 |
| transaction_amount_last_24_hours_paise | txn_amount_last_24h_paise     | 110000 |    110000 |            100 |                    0 |            0 |
| is_new_city                            | is_new_city                   | 110000 |    110000 |            100 |                    0 |            0 |
| has_recent_failures                    | has_recent_failures           | 110000 |    110000 |            100 |                    0 |            0 |
| is_new_account                         | is_new_account                | 110000 |    110000 |            100 |                    0 |            0 |
| hour_of_day                            | hour_of_day                   | 110000 |    110000 |            100 |                    0 |            0 |

## Reason codes

Exact reason-code set match: **100.000%** (110,000/110,000)

| reason_code         |   match_rate_% |   mine_fired |   provided_fired |
|:--------------------|---------------:|-------------:|-----------------:|
| R01_NEW_DEVICE      |            100 |         7305 |             7305 |
| R02_GEO_MISMATCH    |            100 |        90293 |            90293 |
| R03_ODD_HOUR        |            100 |        15438 |            15438 |
| R04_FAILED_ATTEMPTS |            100 |         9877 |             9877 |
| R05_AMOUNT_SPIKE    |            100 |         3068 |             3068 |
| R06_NEW_ACCOUNT     |            100 |         1109 |             1109 |
| R07_VELOCITY        |            100 |        14509 |            14509 |
| R08_HIGH_RISK_MCC   |            100 |        32602 |            32602 |

## Mismatches and what explains them

No row disagrees after applying the documented conventions below. Those conventions are the *explanations* for every difference I saw while building the pipeline (each one produced a lower match rate until fixed):

| Difference seen while building | Cause | Fix | Match rate before -> after |
|---|---|---|---|
| amount_to_average_ratio | I first averaged only SUCCESS payments; the client's definition averages every prior authorisation **attempt** (declines count) | use all attempts | 63.2% -> 100% |
| rounding | provided table stores ratio to 4 dp and distance to 2 dp | compare with tolerance 1e-4 / 0.011 km | float noise -> 100% |
| first transaction of a customer | no 90-day history, so ratio is undefined | keep NaN on both sides (never fill with 0 or 1) | counted as agreement when both are null |
| missing device / location | feature is unknown, not False | keep null; null on both sides counts as a match | null disagreements = 0 |
| failures window | an outcome that arrives after the transaction must not count | only FAILED with outcome_time <= transaction_time inside the last 24h | leakage removed |
| same-second transactions | ties could let a row see itself | closed='left' windows + sort by customer, time, transaction_id | current row excluded |
