import os
import django
from dotenv import load_dotenv
import pandas as pd



os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

load_dotenv()

API_KEY = os.environ.get("CONGRESS_API_KEY")


django.setup()
from server.models import (
    Stock,
    Sector,
)




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
    # Create our placeholder
    Sector.objects.get_or_create(
        sector_code="00",
        defaults={"sector_name": "Other", "description": "Other or misc. sectors"}
    )
    
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





if __name__ == "__main__":
    getStocks()
