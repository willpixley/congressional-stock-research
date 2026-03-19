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
    Committee,
    Stock,
    Sector,
    CommitteeMembership,
    Trade,
    Congress
)


us_states_territories = {
    "Alabama": "AL",
    "Alaska": "AK",
    "American Samoa": "AS",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Guam": "GU",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Marshall Islands": "MH",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Northern Mariana Islands": "MP",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Palau": "PW",
    "Pennsylvania": "PA",
    "Puerto Rico": "PR",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virgin Islands": "VI",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}

# insert congress 112-119
def insert_congresses():
    congresses = [(n, 1947 + (n - 80) * 2, 1949 + (n - 80) * 2) for n in range(80, 120)]
    for number, start, end in congresses:
        Congress.objects.get_or_create(
            congress_number=number,
            defaults={
                'start_year': date(start, 1, 3),
                'end_year': date(end, 1, 3),
            }
        )

## Good. Does not add stock sectors


# Manually inserted these stocks:
# All sectors are 00 as they are just placeholders for when I assign sectors later. Some are bankrupt or are on foreign stock exchanges
manually_inserted_stocks = [
    {"ticker": "WBA", "name": "Walgreens Boots Alliance Inc", "sector": "00"},
    {"ticker": "ALXN", "name": "Alexion Pharmaceuticals Inc", "sector": "00"},
    {"ticker": "CELG", "name": "Celgene Corp", "sector": "00"},
    {"ticker": "CORE", "name": "Core-Mark Holding Company Inc", "sector": "00"},
    {"ticker": "AGN", "name": "Allergan", "sector": "00"},
    {"ticker": "CBPX", "name": "Continental Building Products", "sector": "00"},
    {"ticker": "LMRK", "name": "Landmark Infrastructure Part", "sector": "00"},
    {"ticker": "ATVI", "name": "Activision Blizzard Inc", "sector": "00"},
    {"ticker": "ABC", "name": "Amerisource Bergen Corp.", "sector": "00"},
    {"ticker": "FEYE", "name": "FireEye Inc.", "sector": "00"},
    {"ticker": "CBS", "name": "CBS Corp", "sector": "00"},
    {"ticker": "CBF", "name": "Cyber_Folks S.A", "sector": "00"},
    {"ticker": "TWTR", "name": "Twitter", "sector": "00"},
    {"ticker": "CERN", "name": "Cerner Corp", "sector": "00"},
    {"ticker": "SPOR", "name": "Sport-Haley Inc.", "sector": "00"},
    {"ticker": "NSRGY", "name": "Nestle S.A.", "sector": "00"},
    {"ticker": "WPX", "name": "WPX", "sector": "00"},
    {"ticker": "UTX", "name": "United Technologies Corporation", "sector": "00"},
    {"ticker": "WB1", "name": "Westamerica Bancorp", "sector": "00"},
    {"ticker": "TFCF", "name": "Twenty-First Century Fox Inc", "sector": "00"},
    {"ticker": "LRLSQ", "name": "Loral Space", "sector": "00"},
    {"ticker": "FLT", "name": "Volatus Aerospace Inc", "sector": "00"}, # Canada?
    {"ticker": "FDC", "name": "FDC Limited", "sector": "00"}, # India
    {"ticker": "ALBK", "name": "Allahabad Bank", "sector": "00"}, # India
]

def getStocks():
    df = pd.read_csv("./data/NASDAQ.csv")
    
    stocks = []
    for _, row in df.iterrows():
        stock = Stock( name=row["Name"], ticker=row["Symbol"])
        stocks.append(stock)
    Stock.objects.bulk_create(stocks, ignore_conflicts=True)
    print("Inserted NASDAQ stocks")

    df = pd.read_csv("./data/nyse-listed.csv")
    stocks = []
    for _, row in df.iterrows():
        stock = Stock(name=row["Company Name"], ticker=row["ACT Symbol"])
        stocks.append(stock)
    count = Stock.objects.bulk_create(stocks, ignore_conflicts=True)
    print(f"inserted {count} stocks from nyse")

    df = pd.read_csv("./data/other-listed.csv")
    stocks = []
    for _, row in df.iterrows():
        stock = Stock(name=row["Company Name"], ticker=row["ACT Symbol"])
        stocks.append(stock)
    count = Stock.objects.bulk_create(stocks, ignore_conflicts=True)
    print(f"inserted {count} stocks from other")


## Adds all sectors - deprecated. Only uses GICS
def getSectors():
    sectors = [
        Sector(
            sector_code="00", sector_name="Other", description="Other or misc. sectors"
        ),
        Sector(
            sector_code="10",
            sector_name="Energy",
            description="Companies involved in oil, gas, coal, and renewable energy.",
        ),
        Sector(
            sector_code="15",
            sector_name="Basic Materials",
            description="Companies that produce chemicals, construction materials, and metals.",
        ),
        Sector(
            sector_code="20",
            sector_name="Industrials",
            description="Businesses in manufacturing, transportation, and services.",
        ),
        Sector(
            sector_code="25",
            sector_name="Consumer Discretionary",
            description="Retail, media, entertainment, and luxury goods companies.",
        ),
        Sector(
            sector_code="30",
            sector_name="Consumer Staples",
            description="Companies providing essential consumer products such as food and beverages.",
        ),
        Sector(
            sector_code="35",
            sector_name="Healthcare",
            description="Pharmaceutical, biotechnology, and medical device companies.",
        ),
        Sector(
            sector_code="40",
            sector_name="Financials",
            description="Banks, investment firms, and insurance companies.",
        ),
        Sector(
            sector_code="45",
            sector_name="Technology",
            description="Software, hardware, and IT services companies.",
        ),
        Sector(
            sector_code="50",
            sector_name="Telecommunications",
            description="Providers of internet, phone, and wireless services.",
        ),
        Sector(
            sector_code="55",
            sector_name="Utilities",
            description="Electric, gas, and water service providers.",
        ),
        Sector(
            sector_code="60",
            sector_name="Real Estate",
            description="Real estate investment trusts (REITs) and property management companies.",
        ),
    ]
    Sector.objects.bulk_create(sectors)




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
                stock = Stock.objects.get(ticker=ticker)
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
    # getSectors()
    # getStocks()
    import_trades_from_csv("./data/all_trades.csv")
    # insert_congresses()
