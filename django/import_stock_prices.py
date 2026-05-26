import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

import duckdb
import pandas as pd
from server.models import Stock, StockPrice

CSV_PATH = "data/wharton_data.csv"
CHUNK_SIZE = 10_000

conn = duckdb.connect()

# --- Filter to tickers in DB ---
tickers = list(Stock.objects.values_list("ticker", flat=True))
tickers_sql = ", ".join(f"'{t}'" for t in tickers)
print(f"Importing for {len(tickers)} tickers...")

# --- Stream through CSV without loading into memory ---
result = conn.execute(
    f"""
    SELECT
        ticker,
        CAST(DlyCalDt AS DATE) AS date,
        DlyPrc AS price,
        TRY_CAST(DlyRet AS DOUBLE) AS ret,
        TRY_CAST(DlyRetx AS DOUBLE) AS retx,
        TRY_CAST(vwretd AS DOUBLE) AS vwretd,
        TRY_CAST(sprtrn AS DOUBLE) AS sprtrn
    FROM read_csv_auto('{CSV_PATH}')
    WHERE DlyPrc > 0
    AND ticker IN ({tickers_sql})
"""
)

total_imported = 0
total_conflicts = 0

while True:
    rows = result.fetchmany(CHUNK_SIZE)
    if not rows:
        break

    df = pd.DataFrame(
        rows, columns=["ticker", "date", "price", "ret", "retx", "vwretd", "sprtrn"]
    )
    df = pd.DataFrame(
        rows, columns=["ticker", "date", "price", "ret", "retx", "vwretd", "sprtrn"]
    )
    for col in ["price", "ret", "retx", "vwretd", "sprtrn"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.replace([float("nan"), "nan", "NaN"], None)

    objs = [
        StockPrice(
            ticker_id=row.ticker,
            date=row.date,
            price=row.price,
            ret=row.ret,
            retx=row.retx,
            vwretd=row.vwretd,
            sprtrn=row.sprtrn,
        )
        for row in df.itertuples()
    ]

    created = StockPrice.objects.bulk_create(objs, ignore_conflicts=True)
    conflicts = len(objs) - len(created)
    total_imported += len(created)
    total_conflicts += conflicts
    print(
        f"  {total_imported:,} imported, {total_conflicts:,} conflicts skipped",
        end="\r",
    )

print(
    f"\nDone. {total_imported:,} rows imported, {total_conflicts:,} conflicts skipped."
)
