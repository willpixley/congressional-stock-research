import sys
import os
from typing import Callable, Iterable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
import django

django.setup()

import pandas as pd
import pandas_market_calendars as mcal
from django.db import connection


def get_prices_from_db(tickers, start_date, end_date) -> pd.DataFrame:
    """date-indexed, ticker-columned, values = retx."""
    placeholders = ",".join(["%s"] * len(tickers))
    query = f"""
        SELECT date, ticker, retx
        FROM server_stockprice
        WHERE ticker IN ({placeholders})
          AND date BETWEEN %s AND %s
        ORDER BY date
    """
    with connection.cursor() as cur:
        cur.execute(query, list(tickers) + [start_date, end_date])
        rows = cur.fetchall()

    df = pd.DataFrame(rows, columns=["date", "ticker", "retx"])
    df["date"] = pd.to_datetime(df["date"])
    df["retx"] = df["retx"].astype(float)
    return df.pivot(index="date", columns="ticker", values="retx")


def build_ctp(
    segments: pd.DataFrame,
    weighting: str = "equal",
) -> pd.Series:
    """
    Calendar-time portfolio returns. `segments` must have:
      buy_date, sell_date, stock_ticker, (buy_amount if value-weighting).
    Returns a date-indexed Series of daily portfolio returns.
    """
    if segments.empty:
        return pd.Series(dtype=float, name="returns")

    df = segments.copy()
    df["buy_date"] = pd.to_datetime(df["buy_date"])
    df["sell_date"] = pd.to_datetime(df["sell_date"])

    start = df["buy_date"].min()
    end = df["sell_date"].max()
    tickers = df["stock_ticker"].unique().tolist()

    returns = get_prices_from_db(tickers, start, end)

    nyse = mcal.get_calendar("NYSE")
    schedule = nyse.schedule(start_date=start, end_date=end)
    all_dates = mcal.date_range(schedule, frequency="1D").normalize().tz_localize(None)

    daily = {}
    for date in all_dates:
        open_pos = df[(df["buy_date"] <= date) & (df["sell_date"] > date)]
        if open_pos.empty or date not in returns.index:
            continue

        rets, weights = [], []
        for _, seg in open_pos.iterrows():
            t = seg["stock_ticker"]
            if t not in returns.columns:
                continue
            r = returns.loc[date, t]
            if pd.isna(r):
                continue
            rets.append(r)

            if weighting == "equal":
                weights.append(1.0)
            elif weighting == "value":
                weights.append(float(seg.get("buy_amount", 1.0)))
            elif weighting == "trade_count":
                weights.append(1.0)
            else:
                raise ValueError(f"unknown weighting: {weighting}")

        if rets:
            w = pd.Series(weights)
            r = pd.Series(rets)
            daily[date] = float((w * r).sum() / w.sum())

    return pd.Series(daily, name="returns").sort_index()


# ---------- stratification: df -> dict[label, df] ----------
# Each stratifier returns a mapping of group label -> filtered segments.
# Compose them by chaining or by writing a custom one.

Stratifier = Callable[[pd.DataFrame], dict[str, pd.DataFrame]]


def strat_all(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {"all": df}


def strat_by_member(min_trades: int = 10) -> Stratifier:
    def _f(df):
        counts = df["member_bio_guide_id"].value_counts()
        keep = counts[counts >= min_trades].index
        return {f"{bio}": df[df["member_bio_guide_id"] == bio] for bio in keep}

    return _f


def strat_by_column(col: str) -> Stratifier:
    """Group by any column: 'party', 'chamber', 'sector_code', etc."""

    def _f(df):
        return {f"{col}={v}": g for v, g in df.groupby(col, dropna=False)}

    return _f


def strat_by_flag(col: str) -> Stratifier:
    """Boolean column: yields '<col>_true' and '<col>_false'."""

    def _f(df):
        return {
            f"{col}_true": df[df[col] == True],
            f"{col}_false": df[df[col] == False],
        }

    return _f


def strat_top_quartile_by_alpha(
    alpha_map: dict[str, float], q: float = 0.75
) -> Stratifier:
    """alpha_map: bio_guide_id -> per-member alpha (your noisy sort signal)."""

    def _f(df):
        import numpy as np

        threshold = np.nanpercentile(list(alpha_map.values()), q * 100)
        top = {bio for bio, a in alpha_map.items() if a is not None and a >= threshold}
        return {f"top_q{int(q*100)}": df[df["member_bio_guide_id"].isin(top)]}

    return _f


def strat_compose(*stratifiers: Stratifier) -> Stratifier:
    """Cross stratifiers: e.g. compose(by_column('chamber'), by_flag('buy_conflicted'))
    yields {'chamber=H AND buy_conflicted_true': ...}."""

    def _f(df):
        out = {"": df}
        for s in stratifiers:
            new = {}
            for prev_label, prev_df in out.items():
                for sub_label, sub_df in s(prev_df).items():
                    label = f"{prev_label} AND {sub_label}" if prev_label else sub_label
                    new[label] = sub_df
            out = new
        return out

    return _f


# ---------- runner ----------


def run(
    segments: pd.DataFrame,
    stratifier: Stratifier = strat_all,
    weighting: str = "equal",
    out_dir: str = "./output",
    min_obs: int = 30,
) -> dict[str, pd.Series]:
    os.makedirs(out_dir, exist_ok=True)
    groups = stratifier(segments)
    print(f"Building {len(groups)} portfolio(s)...")

    results = {}
    for label, sub in groups.items():
        if sub.empty:
            print(f"  [skip] {label}: empty")
            continue
        print(
            f"  {label}: {len(sub)} segments, {sub['member_bio_guide_id'].nunique()} members"
        )
        ret = build_ctp(sub, weighting=weighting)
        if len(ret) < min_obs:
            print(f"    [skip] only {len(ret)} return obs")
            continue
        results[label] = ret
        safe = label.replace("/", "_").replace(" ", "_").replace("=", "-")
        ret.to_csv(f"{out_dir}/{safe}.csv")
    return results


def strat_member_list(bio_ids: Iterable[str], label: str = "selected") -> Stratifier:
    """Pool a specific list of members into one portfolio."""
    bio_set = set(bio_ids)

    def _f(df):
        return {label: df[df["member_bio_guide_id"].isin(bio_set)]}

    return _f


# ---------- examples ----------

if __name__ == "__main__":
    df = pd.read_csv("./data/trade_segments.csv")

    positive_ids = [
        "F000246",
        "B001297",
        "S001189",
        "G000061",
        "N000192",
        "M001203",
        "L000594",
        "B001248",
        "J000310",
        "M001199",
        "W000797",
        "T000461",
        "M001198",
        "B001274",
        "R000307",
        "G000590",
        "P000197",
        "L000579",
        "G000551",
        "M000934",
        "I000024",
        "B001292",
        "H001086",
        "J000307",
        "L000601",
        "D000617",
        "P000612",
        "S001190",
        "E000296",
        "L000397",
        "C001123",
        "A000378",
        "J000020",
        "P000609",
        "S001201",
        "M001213",
        "R000122",
        "C001071",
        "B001236",
        "K000375",
        "W000821",
        "S001211",
        "S000250",
        "F000468",
        "S001229",
        "H000636",
    ]
    # run(
    #     df,
    #     strat_member_list(positive_ids, label="positive_alpha"),
    #     out_dir="./output/positive_alpha",
    # )

    # 1. Single pooled CTP
    # run(df, strat_all, out_dir="./output/pooled")

    # # 2. By chamber
    # run(df, strat_by_column("chamber"), out_dir="./output/by_chamber")
    # run(df, strat_by_column("party"), out_dir="./output/by_party")

    # # 3. By party × conflicted flag
    run(
        df,
        strat_compose(strat_by_flag("buy_conflicted")),
        out_dir="./output/conflicted",
    )

    # # 4. Per-member (your old behavior)
    # run(df, strat_by_member(min_trades=10), out_dir="./output/per_member")

    # # 5. Top quartile by your existing per-member alphas
    # # import json

    # # alphas = {
    # #     d["bio_guide_id"]: d["ff5"]["alpha_annualized"]
    # #     for d in json.load(open("./data/alphas.json"))
    # #     if d["ff5"] is not None
    # # }
    # # run(df, strat_top_quartile_by_alpha(alphas), out_dir="./output/top_q")
