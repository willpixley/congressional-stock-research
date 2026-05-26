import os
import django
import requests
from dotenv import load_dotenv
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
load_dotenv()
django.setup()

from server.models import Committee, Hearing, Congress

API_KEY = os.environ.get("CONGRESS_API_KEY")
BASE_URL = "https://api.congress.gov/v3"
CHAMBERS = ["house", "senate"]
DELAY = 0.5


def get_paginated(url, params=None):
    """Yield items from a paginated congress.gov endpoint."""
    params = params or {}
    params.update({"api_key": API_KEY, "format": "json", "limit": 250, "offset": 0})
    while True:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        hearings = data.get("hearings", [])
        yield from hearings
        pagination = data.get("pagination", {})
        if params["offset"] + params["limit"] >= pagination.get("count", 0):
            break
        params["offset"] += params["limit"]
        time.sleep(DELAY)


def scrape_hearing_list(congress_number):
    """Phase 1: collect jacket numbers for all hearings in a congress."""
    results = []
    for chamber in CHAMBERS:
        url = f"{BASE_URL}/hearing/{congress_number}/{chamber}"
        for item in get_paginated(url):
            results.append(
                {
                    "jacket_no": str(item["jacketNumber"]).zfill(5),  # pad if needed
                    "chamber": item["chamber"][0].upper(),  # "House" -> "H"
                    "congress": item["congress"],
                }
            )
    return results


def scrape_hearing_detail(congress_number, chamber_str, jacket_no):
    """
    Phase 2: fetch detail for a single hearing.
    chamber_str should be 'house' or 'senate' (lowercase for URL).
    Returns dict with committees, title, and transcript text (if available).
    """
    url = f"{BASE_URL}/hearing/{congress_number}/{chamber_str}/{jacket_no}"
    resp = requests.get(url, params={"api_key": API_KEY, "format": "json"})
    resp.raise_for_status()
    data = resp.json().get("hearing", {})

    # Grab transcript text URL if present
    transcript_text = None
    for fmt in data.get("formats", []):
        if fmt.get("type") == "Formatted Text":
            txt_resp = requests.get(fmt["url"])
            if txt_resp.ok:
                transcript_text = txt_resp.text
            break

    committee_codes = [
        c.get("systemCode") for c in data.get("committees", []) if c.get("systemCode")
    ]

    return {
        "title": data.get("title"),
        "transcript": transcript_text,
        "committee_codes": committee_codes,
    }


def run(congress_numbers: list[int]):
    # Phase 1: collect all jacket numbers
    print("Phase 1: listing hearings...")
    hearing_stubs = []
    for cn in congress_numbers:
        stubs = scrape_hearing_list(cn)
        print(f"  Congress {cn}: {len(stubs)} hearings found")
        hearing_stubs.extend(stubs)

    # Phase 2: fetch detail and upsert
    print(f"\nPhase 2: fetching {len(hearing_stubs)} hearing details...")
    for i, stub in enumerate(hearing_stubs):
        jacket_no = stub["jacket_no"]
        chamber_str = "house" if stub["chamber"] == "H" else "senate"
        congress_number = stub["congress"]

        try:
            detail = scrape_hearing_detail(congress_number, chamber_str, jacket_no)
        except requests.HTTPError as e:
            print(f"  [{i+1}] {jacket_no} failed: {e}")
            continue

        congress = Congress.objects.get(congress_number=congress_number)

        hearing, created = Hearing.objects.update_or_create(
            jacket_no=jacket_no,
            defaults={
                "congress": congress,
                "chamber": stub["chamber"],
                "title": detail["title"],
                "transcript": detail["transcript"],
            },
        )

        # Resolve committees by systemCode (matches committee_code PK)
        committees = Committee.objects.filter(
            committee_code__in=detail["committee_codes"]
        )
        hearing.committees.set(committees)

        status = "created" if created else "updated"
        print(
            f"  [{i+1}/{len(hearing_stubs)}] {jacket_no} {status} "
            f"({committees.count()}/{len(detail['committee_codes'])} committees matched)"
        )

        time.sleep(DELAY)

    print("Done.")


if __name__ == "__main__":
    # Adjust congress numbers as needed
    run(congress_numbers=range(112, 120))
