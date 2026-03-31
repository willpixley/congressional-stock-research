# From https://www.census.gov/programs-surveys/economic-census/year/2022/guidance/understanding-naics.html#naics-structure

# SIC to NAICS crosswalk downloaded from https://www.naics.com/naics-to-sic-crosswalk-2/


import pandas as pd
import os
import django
import pandas as pd

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")


django.setup()
from server.models import Stock, Sector

NAICS_SECTORS = {
    "11": "Agriculture, Forestry, Fishing and Hunting",
    "21": "Mining, Quarrying, and Oil and Gas Extraction",
    "22": "Utilities",
    "23": "Construction",
    "31": "Manufacturing",
    "32": "Manufacturing",
    "33": "Manufacturing",
    "42": "Wholesale Trade",
    "44": "Retail Trade",
    "45": "Retail Trade",
    "48": "Transportation and Warehousing",
    "49": "Transportation and Warehousing",
    "51": "Information",
    "52": "Finance and Insurance",
    "53": "Real Estate and Rental and Leasing",
    "54": "Professional, Scientific, and Technical Services",
    "55": "Management of Companies and Enterprises",
    "56": "Administrative and Support and Waste Management and Remediation Services",
    "61": "Educational Services",
    "62": "Health Care and Social Assistance",
    "71": "Arts, Entertainment, and Recreation",
    "72": "Accommodation and Food Services",
    "81": "Other Services (except Public Administration)",
    "92": "Public Administration",
}


def get_or_create_sector(naics_code):
    prefix = str(naics_code)[:2]
    sector_name = NAICS_SECTORS.get(prefix)
    if not sector_name:
        return None
    sector, _ = Sector.objects.get_or_create(
        sector_code=prefix, defaults={"sector_name": sector_name}
    )
    return sector


def build_sic_to_naics(crosswalk_path):
    df = pd.read_csv(
        crosswalk_path, dtype=str, usecols=["Related SIC Code", "2022 NAICS Code"]
    )
    df = df.dropna(subset=["Related SIC Code", "2022 NAICS Code"])
    return dict(
        zip(df["Related SIC Code"].str.strip(), df["2022 NAICS Code"].str.strip())
    )


def import_stocks(stock_csv_path, crosswalk_path):
    sic_to_naics = build_sic_to_naics(crosswalk_path)

    df = pd.read_csv(stock_csv_path, dtype=str)
    df["NAICS"] = df["NAICS"].fillna("0").str.strip()
    df["SICCD"] = df["SICCD"].fillna("0").str.strip()
    df["SecInfoStartDt"] = pd.to_datetime(df["SecInfoStartDt"])

    created = 0
    updated = 0
    skipped = 0

    for ticker, group in df.groupby("ticker"):
        # Sort by most recently assigned first
        group = group.sort_values("SecInfoStartDt", ascending=False)

        name = group["IssuerNm"].iloc[0]

        # Get most recent naics
        valid_naics = group[group["NAICS"] != "0"]["NAICS"]
        if not valid_naics.empty:
            naics_code = valid_naics.iloc[0]
        else:
            # use the crosswalk from SIC
            sic = group["SICCD"].iloc[0].zfill(4)
            naics_code = sic_to_naics.get(sic)
            if not naics_code:
                # match to 2 digits
                sic3 = sic[:2]
                naics_code = next(
                    (v for k, v in sic_to_naics.items() if k.startswith(sic3)), None
                )
            if not naics_code:
                print(f"No NAICS found for {ticker} (SIC: {sic})")
                skipped += 1
                # Still create stock without sector
                Stock.objects.get_or_create(ticker=ticker, defaults={"name": name})
                continue

        sector = get_or_create_sector(naics_code)

        if not sector:
            print(f"No sector mapping for NAICS {naics_code} ({ticker})")
            skipped += 1
            Stock.objects.get_or_create(ticker=ticker, defaults={"name": name})
            continue

        Stock.objects.get_or_create(
            ticker=ticker, defaults={"name": name, "sector": sector}
        )

        created += 1

    print(f"Created: {created}, Updated: {updated}, Skipped (no sector): {skipped}")


if __name__ == "__main__":
    import_stocks("./data/ticker_data.csv", "./data/SIC_to_NAICS.csv")
