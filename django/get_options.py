"""
End-to-end pipeline: parse option contracts from PTR description strings,
reconstruct OCC symbols, and fetch the historical option price from yfinance
on the trade date.
"""

import re
import time
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

INPUT_CSV = Path("./data/all_trades.csv")
PARSED_CSV = Path("parsed_options.csv")
UNPARSED_TXT = Path("unparsed_descriptions.txt")
PRICES_CSV = Path("option_prices.csv")
FAILED_CSV = Path("option_prices_failed.csv")

DESCRIPTION_COL = "Description"
TICKER_COL = "Ticker"
TRADE_DATE_COL = "Traded"

SLEEP_BETWEEN_REQUESTS = 0.5  # seconds, to avoid rate-limiting


@dataclass
class OptionContract:
    underlying: str
    option_type: str  # "C" or "P"
    strike: float
    expiration: datetime
    raw_type: str  # original phrasing for audit

    @property
    def occ_symbol(self) -> str:
        """OCC 21-char format used by yfinance: TICKER + YYMMDD + C/P + strike*1000 (8 digits)."""
        exp = self.expiration.strftime("%y%m%d")
        strike_int = int(round(self.strike * 1000))
        return f"{self.underlying.upper()}{exp}{self.option_type}{strike_int:08d}"


# ---- regex patterns ----
CALL_PATTERNS = re.compile(r"\bcall\b", re.IGNORECASE)
PUT_PATTERNS = re.compile(r"\b(put|short sale)\b", re.IGNORECASE)

STRIKE_RE = re.compile(
    r"strike\s*price[^$\d]*\$?\s*([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)
STRIKE_FALLBACK_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")

EXPIRES_RE = re.compile(
    r"(?:expires?|expiration[^:\d]*[:\s]?)\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)
DATE_FALLBACK_RE = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")

OPTION_KEYWORDS_RE = re.compile(
    r"\b(call|put|option|strike|expir|short sale)\b",
    re.IGNORECASE,
)


def _parse_date(s: str) -> Optional[datetime]:
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def looks_like_option(description: str) -> bool:
    """Heuristic: skip descriptions that clearly aren't about options."""
    if not description:
        return False
    return bool(OPTION_KEYWORDS_RE.search(description))


def parse_option_description(
    description: str,
    underlying: str,
) -> Optional[OptionContract]:
    if not description or not underlying:
        return None
    text = description.strip()

    # Option type
    if CALL_PATTERNS.search(text):
        opt_type, raw = "C", "call"
    elif PUT_PATTERNS.search(text):
        m = PUT_PATTERNS.search(text)
        opt_type, raw = "P", m.group(0).lower()
    else:
        return None

    # Strike
    m = STRIKE_RE.search(text)
    if not m:
        m = STRIKE_FALLBACK_RE.search(text)
    if not m:
        return None
    strike = float(m.group(1).replace(",", ""))

    # Expiration
    exp = None
    m = EXPIRES_RE.search(text)
    if m:
        exp = _parse_date(m.group(1))
    else:
        dates = DATE_FALLBACK_RE.findall(text)
        if len(dates) >= 2:
            exp = _parse_date(dates[-1])
        elif len(dates) == 1 and "purchas" not in text.lower():
            exp = _parse_date(dates[0])

    if exp is None:
        return None

    return OptionContract(
        underlying=underlying,
        option_type=opt_type,
        strike=strike,
        expiration=exp,
        raw_type=raw,
    )


def parse_trades(df: pd.DataFrame) -> tuple[pd.DataFrame, set[str]]:
    """
    Parse option contracts from each row. Returns parsed DataFrame plus the
    set of descriptions that could not be parsed.
    """
    for col in (DESCRIPTION_COL, TICKER_COL, TRADE_DATE_COL):
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in {INPUT_CSV}")

    parsed_rows = []
    unparsed: set[str] = set()

    for idx, row in df.iterrows():
        desc = row[DESCRIPTION_COL]
        ticker = row[TICKER_COL]

        if pd.isna(desc) or not str(desc).strip():
            continue

        desc_str = str(desc).strip()
        ticker_str = str(ticker).strip() if not pd.isna(ticker) else ""

        contract = parse_option_description(desc_str, ticker_str)
        if contract is None:
            unparsed.add(desc_str)
            continue

        parsed_rows.append(
            {
                "row_index": idx,
                "ticker": ticker_str,
                "description": desc_str,
                "trade_date": row[TRADE_DATE_COL],
                **asdict(contract),
                "occ_symbol": contract.occ_symbol,
            }
        )

    return pd.DataFrame(parsed_rows), unparsed


def fetch_price_on_date(occ_symbol: str, trade_date: pd.Timestamp) -> dict:
    """
    Pull OHLC for the contract on (or near) trade_date.

    Requests a small window centered on trade_date and picks the exact day if
    present, else the closest prior trading day.
    """
    start = (trade_date - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
    end = (trade_date + pd.Timedelta(days=2)).strftime("%Y-%m-%d")

    try:
        hist = yf.Ticker(occ_symbol).history(start=start, end=end, auto_adjust=False)
    except Exception as e:
        print(f"fetch_error: {e}")
        return {"error": f"fetch_error: {e}"}

    if hist.empty:
        return {"error": "no_data"}

    hist.index = pd.to_datetime(hist.index).date
    target = trade_date.date()

    if target in hist.index:
        bar = hist.loc[target]
        match_kind = "exact"
        match_date = target
    else:
        prior = [d for d in hist.index if d <= target]
        if not prior:
            return {"error": "no_prior_bar"}
        match_date = max(prior)
        bar = hist.loc[match_date]
        match_kind = "nearest_prior"

    return {
        "open": float(bar["Open"]),
        "high": float(bar["High"]),
        "low": float(bar["Low"]),
        "close": float(bar["Close"]),
        "volume": int(bar["Volume"]) if not pd.isna(bar["Volume"]) else None,
        "match_kind": match_kind,
        "match_date": str(match_date),
        "error": None,
    }


def fetch_prices(parsed_df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Fetch yfinance prices for each parsed contract. Returns (results, failures)."""
    parsed_df = parsed_df.copy()
    parsed_df["trade_date"] = pd.to_datetime(parsed_df["trade_date"], errors="coerce")

    missing = parsed_df["trade_date"].isna().sum()
    if missing:
        print(f"Warning: {missing} rows have unparseable trade dates; skipping those.")

    results: list[dict] = []
    failures: list[dict] = []
    total = len(parsed_df)

    for i, (_, row) in enumerate(parsed_df.iterrows()):
        if pd.isna(row["trade_date"]):
            continue

        price = fetch_price_on_date(row["occ_symbol"], row["trade_date"])

        record = {
            "row_index": row["row_index"],
            "ticker": row["ticker"],
            "occ_symbol": row["occ_symbol"],
            "option_type": row["option_type"],
            "strike": row["strike"],
            "expiration": row["expiration"],
            "trade_date": row["trade_date"].strftime("%Y-%m-%d"),
            **price,
        }

        if price.get("error"):
            failures.append(record)
        else:
            print("Success")
            results.append(record)

        if (i + 1) % 25 == 0:
            print(f"  processed {i + 1}/{total}")

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    return results, failures


def main():
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df)} rows from {INPUT_CSV}")

    parsed_df, unparsed = parse_trades(df)
    parsed_df.to_csv(PARSED_CSV, index=False)
    UNPARSED_TXT.write_text("\n---\n".join(sorted(unparsed)))

    print(f"Parsed: {len(parsed_df)} contracts")
    print(f"Unparsed descriptions: {len(unparsed)}")

    if parsed_df.empty:
        print("No contracts parsed; nothing to fetch.")
        return

    print(f"\nFetching yfinance prices for {len(parsed_df)} contracts...")
    results, failures = fetch_prices(parsed_df)

    pd.DataFrame(results).to_csv(PRICES_CSV, index=False)
    pd.DataFrame(failures).to_csv(FAILED_CSV, index=False)

    print(f"\nFetched prices: {len(results)}")
    print(f"Failed lookups: {len(failures)}")
    if failures:
        reasons = Counter(f["error"].split(":")[0] for f in failures)
        print("Failure breakdown:")
        for reason, count in reasons.most_common():
            print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()
