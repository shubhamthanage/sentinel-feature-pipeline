# SENTINEL data quality report

## 1. Rows per split (transactions)

| split      |   rows |
|:-----------|-------:|
| warmup     |  10000 |
| train      |  72050 |
| validation |  14061 |
| holdout    |  13889 |

Total: **110,000**

Labels per split:

| split      |   labels |   fraud |   fraud_rate |
|:-----------|---------:|--------:|-------------:|
| warmup     |    10000 |      60 |      0.006   |
| train      |    72050 |     438 |      0.00608 |
| validation |    14061 |      89 |      0.00633 |
| holdout    |    13889 |      73 |      0.00526 |


## 2. Nulls per column

**customers** (2,500 rows): no nulls

**merchants** (200 rows): no nulls

**devices** (10,120 rows): no nulls

**transactions** (110,000 rows): `device_id`=1,138 (1.03%), `customer_location`=3,257 (2.96%), `average_transaction_value`=2,829 (2.57%)

**payment_outcomes** (110,000 rows): `failure_code`=97,985 (89.08%)

**labels** (110,000 rows): no nulls

**features** (110,000 rows): `amount_to_avg_ratio`=2,829 (2.57%), `is_new_device`=1,138 (1.03%), `customer_merchant_distance_km`=3,257 (2.96%), `is_new_city`=3,257 (2.96%), `distinct_customers_per_device_7d`=1,138 (1.03%)


## 3. Duplicates

| table | duplicate keys | fully duplicated rows |
|---|---|---|
| customers | 0 | 0 |
| merchants | 0 | 0 |
| devices | 0 | 0 |
| transactions | 0 | 0 |
| payment_outcomes | 0 | 0 |
| labels | 0 | 0 |
| features | 0 | 0 |

Same customer + merchant + amount + timestamp (different ids): **0**


## 4. Wrong types / invalid values

| check | rows affected |
|---|---|
| transaction_time not parseable | 0 |
| transaction_amount not numeric | 0 |
| amount <= 0 | 0 |
| amount_paise != round(amount*100) | 0 |
| customer_location present but not valid JSON lat/lon | 0 |
| merchant_location present but not valid JSON lat/lon | 0 |
| customers.created_at not parseable | 0 |
| transaction before account creation | 0 |
| fraud_label not in {0,1} | 0 |
| payment status not SUCCESS/FAILED | 0 |

Column dtypes (transactions):

```
transaction_id                   str
customer_id                      str
merchant_id                      str
device_id                        str
amount_paise                   int64
transaction_amount           float64
payment_channel                  str
merchant_category                str
transaction_time                 str
customer_age                   int64
customer_location                str
merchant_location                str
account_age                    int64
previous_transactions          int64
average_transaction_value    float64
failed_transactions            int64
split                            str
is_synthetic                    bool
```


## 5. Outliers in transaction_amount

|       |           amount |
|:------|-----------------:|
| count | 110000           |
| mean  |   4478.12        |
| std   |  95799.6         |
| min   |      8.2         |
| 50%   |   1250.34        |
| 90%   |   5663.04        |
| 99%   |  25242.9         |
| 99.9% | 116931           |
| max   |      7.99593e+06 |

- Raw IQR rule (> Q3 + 1.5*IQR = 5,920): **10,344** rows (9.40%)
- IQR on log(amount): **1,382** rows (1.26%)
- Fraud rate among raw-IQR outliers: 4.756% vs 0.169% for the rest

Amounts are heavy-tailed (not normal), so I report outliers but do **not** delete them: big amounts are real signal for the amount-spike reason code.


## 6. Time range per split

| split      | min                              | max                              |
|:-----------|:---------------------------------|:---------------------------------|
| warmup     | 2024-09-30 18:35:15.602000+00:00 | 2024-12-31 18:09:03.133000+00:00 |
| train      | 2024-12-31 19:07:56.971000+00:00 | 2025-10-31 18:16:30.969000+00:00 |
| validation | 2025-10-31 18:44:47.012000+00:00 | 2025-12-31 18:04:31.050000+00:00 |
| holdout    | 2025-12-31 19:36:56.017000+00:00 | 2026-02-28 18:07:27.471000+00:00 |

