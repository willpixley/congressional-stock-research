import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
import django

django.setup()

import pandas as pd
from django.db import connection


def get_prices_from_db(tickers, start_date, end_date):
    placeholders = ",".join(["%s"] * len(tickers))
    query = f"""
        SELECT date, ticker, price
        FROM server_stockprice
        WHERE ticker IN ({placeholders})
          AND date BETWEEN %s AND %s
        ORDER BY date
    """
    with connection.cursor() as cursor:
        cursor.execute(query, tickers + [start_date, end_date])
        rows = cursor.fetchall()

    df = pd.DataFrame(rows, columns=["date", "ticker", "price"])
    df["date"] = pd.to_datetime(df["date"])
    df["price"] = df["price"].astype(float)
    return df.pivot(index="date", columns="ticker", values="price")


def check_coverage(tickers, start_date, end_date):
    """Compare DB coverage against NYSE trading calendar."""
    try:
        import pandas_market_calendars as mcal
    except ImportError:
        print("pip install pandas-market-calendars")
        return

    nyse = mcal.get_calendar("NYSE")
    schedule = nyse.schedule(start_date=start_date, end_date=end_date)
    trading_days = (
        mcal.date_range(schedule, frequency="1D").normalize().tz_localize(None)
    )

    returns = get_prices_from_db(tickers, start_date, end_date)

    missing_days = set(trading_days) - set(returns.index)
    extra_days = set(returns.index) - set(trading_days)

    print("=== Trading Day Coverage ===")
    print(f"Expected {len(trading_days)} trading days, got {len(returns.index)}")
    print(f"Missing trading days: {len(missing_days)}")
    print(f"Unexpected dates (weekends/holidays): {len(extra_days)}")
    if extra_days:
        print(f"  {sorted(extra_days)}")

    print("\n=== NaN Counts per Ticker ===")
    na_counts = returns.isna().sum()
    na_counts = na_counts[na_counts > 0].sort_values(ascending=False)
    if na_counts.empty:
        print("No NaNs found.")
    else:
        for ticker, count in na_counts.items():
            pct = count / len(trading_days) * 100
            print(f"  {ticker}: {count} ({pct:.1f}%)")

    return returns


def find_gap_ranges(tickers, start_date, end_date):
    """Find contiguous NaN blocks per ticker to identify import gaps."""
    returns = get_prices_from_db(tickers, start_date, end_date)

    print("=== Gap Ranges per Ticker ===")
    any_gaps = False
    for ticker in returns.columns:
        s = returns[ticker]
        if not s.isna().any():
            continue

        any_gaps = True
        blocks = []
        in_block = False
        for date, val in s.items():
            if pd.isna(val) and not in_block:
                block_start = date
                in_block = True
            elif not pd.isna(val) and in_block:
                blocks.append((block_start, date, (date - block_start).days))
                in_block = False
        if in_block:
            blocks.append((block_start, s.index[-1], (s.index[-1] - block_start).days))

        print(f"\n{ticker}: {len(blocks)} gap(s)")
        for b in sorted(blocks, key=lambda x: -x[2])[:5]:
            print(f"  {b[0].date()} -> {b[1].date()} ({b[2]} days)")

    if not any_gaps:
        print("No gaps found.")


def check_db_extents(tickers):
    """Show MIN/MAX date and row count per ticker directly from DB."""
    placeholders = ",".join(["%s"] * len(tickers))
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT ticker, MIN(date), MAX(date), COUNT(*)
            FROM server_stockprice
            WHERE ticker IN ({placeholders})
            GROUP BY ticker
            ORDER BY ticker
            """,
            tickers,
        )
        rows = cursor.fetchall()

    print("=== DB Extents per Ticker ===")
    print(f"{'Ticker':<10} {'Min Date':<14} {'Max Date':<14} {'Rows':>8}")
    print("-" * 50)
    for ticker, min_date, max_date, count in rows:
        print(f"{ticker:<10} {str(min_date):<14} {str(max_date):<14} {count:>8}")

    missing = set(tickers) - {r[0] for r in rows}
    if missing:
        print(f"\nTickers with NO data in DB: {missing}")


def audit_bfill(tickers, start_date, end_date, limit=3):
    """Show how many values bfill patches vs. leaves as NaN."""
    raw = get_prices_from_db(tickers, start_date, end_date)
    filled = raw.bfill(limit=limit)

    patched = raw.isna() & filled.notna()
    still_missing = filled.isna()

    print("=== bfill Audit ===")
    print(f"Rows patched by bfill(limit={limit}): {patched.sum().sum()}")
    print(f"Still NaN after bfill: {still_missing.sum().sum()}")

    patched_by_ticker = patched.sum().sort_values(ascending=False)
    patched_by_ticker = patched_by_ticker[patched_by_ticker > 0]
    if not patched_by_ticker.empty:
        print("\nPatches by ticker:")
        for ticker, count in patched_by_ticker.items():
            print(f"  {ticker}: {count}")


def flag_outliers(tickers, start_date, end_date, pct_threshold=0.5, min_price=0.01):
    """Flag suspicious prices: zero/negative, or day-over-day change exceeding threshold."""
    prices = get_prices_from_db(tickers, start_date, end_date)

    print(f"=== Outliers ===")

    # Zero or negative prices
    bad_prices = prices[prices <= min_price].stack()
    if not bad_prices.empty:
        print(f"Zero/negative prices ({len(bad_prices)} found):")
        print(bad_prices.to_string())

    # Large day-over-day moves (possible unadjusted splits)
    daily_chg = prices.pct_change().abs()
    outliers = daily_chg[daily_chg > pct_threshold].stack().sort_values(ascending=False)
    if not outliers.empty:
        print(f"\nDay-over-day moves > {pct_threshold:.0%} ({len(outliers)} found):")
        print(outliers.to_string())

    if bad_prices.empty and outliers.empty:
        print("None found.")


if __name__ == "__main__":
    df = pd.read_csv("./data/closed_trade_segments.csv")

    BIO_GUIDE_ID = "M001136"
    member_df = df[df["member_bio_guide_id"] == BIO_GUIDE_ID]

    start_date = member_df["buy_date"].min()
    end_date = member_df["sell_date"].max()
    tickers = member_df["stock_ticker"].unique().tolist()

    print(f"Validating {len(tickers)} tickers from {start_date} to {end_date}\n")

    check_db_extents(tickers)
    print()
    check_coverage(tickers, start_date, end_date)
    print()
    find_gap_ranges(tickers, start_date, end_date)
    print()
    audit_bfill(tickers, start_date, end_date)
    print()
    flag_outliers(tickers, start_date, end_date)
