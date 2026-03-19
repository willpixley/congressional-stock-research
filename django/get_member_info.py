# get_member_info.py

import os
import django
import requests
from dotenv import load_dotenv
import time



os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

load_dotenv()

API_KEY = os.environ.get("CONGRESS_API_KEY")


django.setup()
from server.models import (
    CongressMember,
    Term,
    Congress
)

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
    Stock,
    Sector,
    Congress
)


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

# Matches party history and term
def get_party_for_term(party_history, term_start_year):
    sorted_history = sorted(party_history, key=lambda p: p['startYear'], reverse=True)
    for party in sorted_history:
        if party['startYear'] <= term_start_year:
            return party['partyAbbreviation']
    return party_history[0]['partyAbbreviation']

## Only gets member bio_guide_ids and leaves everything else blank. 
def getMemberIds():
    members_of_congress = []
    for c in range(112, 120):
        url = f"https://api.congress.gov/v3/member/congress/{c}"
        for i in range(0, 4):
            params = {
                "api_key": API_KEY,
                "limit": 250,
                "current_member": "false",
                "offset": 250 * i,
            }
            response = requests.get(url, params=params)
            members = response.json()["members"]
            for member in members:
   
                bio_guide_id = member["bioguideId"]
   
                members_of_congress.append(
                    CongressMember(
                        bio_guide_id=bio_guide_id,
                    )
                )
    CongressMember.objects.bulk_create(members_of_congress, ignore_conflicts=True)
    print(f"{len(members_of_congress)} members added")

# Given a bio_guide_id, call the congress api to get detailed member information
# Should populate terms as well
def getMemberInfo(bio_guide_id):
    url = f'https://api.congress.gov/v3/member/{bio_guide_id}'
    params = {"api_key": API_KEY}
    response = requests.get(url, params=params)
    member = response.json()['member']
    member_obj = CongressMember.objects.get(bio_guide_id=bio_guide_id)
    member_obj.first_name = member['firstName']
    member_obj.last_name = member['lastName']
    member_obj.inverse_name = member['invertedOrderName']
    member_obj.full_name = member['directOrderName']
    member_obj.save()

    # Update terms
    terms = member['terms']
    for term in terms:
        congress = term['congress']
        chamber = term['chamber'][0]
        state = term['stateCode']
        party = get_party_for_term(member['partyHistory'], term['startYear'])
        print(party)
        term = Term.objects.create(
            congress_id=congress,
            member_id=bio_guide_id,
            chamber=chamber,
            party=party,
            state=state
        )

    print(f"Updated terms and info for {member['directOrderName']}")

    

# Iterate through all members without first name in the db and call getMemberInfo
def getAllMemberData():
    for member in CongressMember.objects.filter(first_name=''):
        getMemberInfo(member.bio_guide_id)
        time.sleep(1)

if __name__ == '__main__':
    insert_congresses()
    getMemberIds()
    getAllMemberData()