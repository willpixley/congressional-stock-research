import os
import django
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
import pandas as pd
import csv
from datetime import datetime, date
from django.db import transaction
from collections import defaultdict
import json


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

load_dotenv()

API_KEY = os.environ.get("CONGRESS_API_KEY")


django.setup()
from server.models import (
    CongressMember,
    Stock,
    Trade,
)






# Gets midpoint of trade size
def parse_trade_size(size_str):
    if not size_str:
        return None

    # Remove $, commas, quotes
    size_str = size_str.replace("$", "").replace(",", "").replace('"', "").strip()

    if "-" not in size_str:
        return None

    lo, hi = size_str.split("-")

    lo = int(lo.strip())
    hi = int(hi.strip())

    # Round lower bound down to nearest 1000
    lo = (lo // 1000) * 1000

    return (lo + hi) // 2


@transaction.atomic
def import_trades_from_csv(path, unmatched_json_path="trade_insert_report.json"):
    # Maps old tickers to new tickers
    ticker_mapping = {
        "VRNG": "XWEL",
        "DISCA": "WBD",
        "SQ": "XYZ",
        "TBK": "TFIN",
    }


    trades_to_create = []

    # ticker -> count
    unmatched_tickers = defaultdict(int)
    invalid_transaction_types = set()

    meta = {
        "rows_processed": 0,
        "trades_inserted": 0,
        "skipped_2023_or_later": 0,
        "invalid_transaction_type_count": 0,
        "missing_members": 0,
        "missing_stocks": 0,
        "other_errors": 0,
        "no_amount_errors": 0
        
    }

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            meta["rows_processed"] += 1
            try:
                trade_date = datetime.strptime(row["Traded"], "%Y-%m-%d").date()
                tx = row["Transaction"].lower()

                if tx == "purchase":
                    trade_type = "B"
                elif tx == "sale" or "sale (full)" or "sale (partial)":
                    trade_type = "S"
                elif tx == "exchange":
                    trade_type = "E"
                else:
                    print("transaction type", tx)
                    meta["invalid_transaction_type_count"] += 1
                    invalid_transaction_types.add(tx)
                    continue

                member = CongressMember.objects.get(bio_guide_id=row["BioGuideID"])
                ticker = ticker_mapping.get(row["Ticker"], row["Ticker"])
                stock, _ = Stock.objects.get_or_create(
                               ticker=ticker,
                                defaults={"name": "unknown", "sector_id": "00"}
                            )
                amount = parse_trade_size(row["Trade_Size_USD"])
                if not amount:
                    meta["no_amount_errors"] += 1
                    continue
                trade = Trade(
                    type=trade_type,
                    stock=stock,
                    date=trade_date,
                    amount=amount,
                    member=member,
                    price_at_trade=0, # Will populate later
                )
                trades_to_create.append(trade)

            # None found
            except CongressMember.DoesNotExist:
                meta["missing_members"] += 1
                print(f"Missing member: {row['BioGuideID']}")

            except Stock.DoesNotExist:
                ticker = row["Ticker"]
                unmatched_tickers[ticker] += 1
                meta["missing_stocks"] += 1
                print(f"Missing stock: {ticker}")

            except Exception as e:
                meta["other_errors"] += 1
                print("Row failed:", e)

    Trade.objects.bulk_create(trades_to_create)
    meta["trades_inserted"] = len(trades_to_create)
    meta["invalid_transaction_types"] = list(invalid_transaction_types)
    unmatched_tickers = dict(unmatched_tickers)
    sorted_unmatched_tickers = dict(sorted(unmatched_tickers.items(), key=lambda x: x[1], reverse=True))

    output = {
        "meta": meta,
        "unmatched_tickers": sorted_unmatched_tickers,
    }

    with open(unmatched_json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Inserted {meta['trades_inserted']} trades")
    print(f"Unmatched tickers: {len(unmatched_tickers)}")


if __name__ == "__main__":
    
    import_trades_from_csv("./data/all_trades.csv")
