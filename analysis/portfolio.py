import pandas as pd
import yfinance as yf
from datetime import timedelta


df = pd.read_csv("../data/closed_trade_segments.csv")


def download_prices(tickers, start, end):
    raw = yf.download(
        tickers,
        start=start,
        end=end + timedelta(days=1),
        auto_adjust=True,
        progress=False,
        session=None,
    )

    if len(tickers) == 1:
        prices = raw[["Open"]].rename(columns={"Open": tickers[0]})
    else:
        prices = raw["Open"]

    # Retry failed tickers individually
    failed = [t for t in tickers if t not in prices.columns or prices[t].isna().all()]
    for ticker in failed:
        for attempt in range(3):
            try:
                single = yf.download(
                    ticker,
                    start=start,
                    end=end + timedelta(days=1),
                    auto_adjust=True,
                    progress=False,
                    session=None,
                )

                if not single.empty:
                    prices[ticker] = single["Open"]
                    print(f"Downloaded f{ticker} indvidually")
                else:
                    print("Empty")
                break
            except Exception as e:
                print(f"Failed to download {ticker}: {e}")
    # Backfill
    return prices.bfill(limit=3)


def get_portfolio_returns(bio_guide_id, df):
    member_df = df[df["member_bio_guide_id"] == bio_guide_id].copy()
    member_df["buy_date"] = pd.to_datetime(member_df["buy_date"])
    member_df["sell_date"] = pd.to_datetime(member_df["sell_date"])

    start_date = member_df["buy_date"].min()
    end_date = member_df["sell_date"].max()

    tickers = member_df["stock_ticker"].unique().tolist()

    prices = download_prices(tickers, start_date, end_date)

    # Get open price on buy date for each segment
    def get_entry_price(row):
        ticker = row["stock_ticker"]
        date = row["buy_date"]
        if ticker not in prices.columns:
            return None
        # Find the first available price on or after buy date
        available = prices.index[prices.index >= date]
        if available.empty:
            return None
        return prices.loc[available[0], ticker]

    member_df["entry_price"] = member_df.apply(get_entry_price, axis=1)
    member_df = member_df.dropna(subset=["entry_price"])

    # Build daily date range
    all_dates = pd.date_range(
        start=start_date, end=end_date, freq="B"
    )  # business days, but includes holidays
    daily_returns = []

    for i, date in enumerate(all_dates):
        # Open positions: bought on or before this date, sold after this date
        open_positions = member_df[
            (member_df["buy_date"] <= date) & (member_df["sell_date"] > date)
        ]

        if open_positions.empty:
            daily_returns.append(0.0)
            continue

        position_returns = []
        for _, seg in open_positions.iterrows():
            ticker = seg["stock_ticker"]
            if ticker not in prices.columns:
                continue
            if date not in prices.index or i == 0:
                continue
            prev_date = all_dates[i - 1]
            if prev_date not in prices.index:
                continue

            price_today = prices.loc[date, ticker]
            price_prev = prices.loc[prev_date, ticker]

            if price_prev == 0:
                continue

            position_returns.append((price_today - price_prev) / price_prev)

        if position_returns:
            daily_returns.append(sum(position_returns) / len(position_returns))
        else:
            daily_returns.append(0.0)

    return pd.Series(daily_returns, index=all_dates, name=bio_guide_id)


# print(df.groupby(["member_bio_guide_id", "member_name"]).size().reset_index(name="trade_count").sort_values("trade_count", ascending=False).head(50))

returns = get_portfolio_returns("C001114", df)
returns.to_csv("returns.csv")
