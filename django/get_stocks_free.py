import os
import django
from dotenv import load_dotenv
import pandas as pd


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

load_dotenv()


django.setup()
from server.models import Stock, Sector


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
    {"ticker": "FLT", "name": "Volatus Aerospace Inc", "sector": "00"},  # Canada?
    {"ticker": "FDC", "name": "FDC Limited", "sector": "00"},  # India
    {"ticker": "ALBK", "name": "Allahabad Bank", "sector": "00"},  # India
]


def getStocks():
    # Create our placeholder
    Sector.objects.get_or_create(
        sector_code="00",
        defaults={"sector_name": "Other", "description": "Other or misc. sectors"},
    )
    df = pd.read_csv("./data/NASDAQ.csv")
    stocks = []
    for _, row in df.iterrows():
        stock = Stock(name=row["Name"], ticker=row["Symbol"])
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


if __name__ == "__main__":
    getStocks()
