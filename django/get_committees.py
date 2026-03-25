import os
import django
import requests
from dotenv import load_dotenv
import time
import pandas as pd


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

load_dotenv()

API_KEY = os.environ.get("CONGRESS_API_KEY")

django.setup()
from server.models import Committee, CommitteeMembership, CongressMember, Term


def get_committees():
    committee_objs = []

    for congress_num in range(112, 120):
        for page in range(3):
            offset = page * 250
            url = f"https://api.congress.gov/v3/committee/{congress_num}"
            params = {
                "api_key": API_KEY,
                "format": "json",
                "limit": 250,
                "offset": offset,
            }
            response = requests.get(url, params=params)
            committees = response.json().get("committees", [])

            if not committees:
                break

            for committee in committees:
                id = committee["systemCode"]
                chamber = committee["chamber"][0].upper()
                name = committee["name"]

                # ignores subcommittees
                if "parent" not in committee:
                    committee_objs.append(
                        Committee(
                            committee_code=id,
                            committee_name=name,
                            chamber=chamber,
                        )
                    )

    created = Committee.objects.bulk_create(committee_objs, ignore_conflicts=True)
    print(f"{len(created)} committees created.")


# Will take about 20 minutes to run. Must call the /committee/chamber/code API to get committee type (standing, joint, etc.)
def get_committee_types():
    committee_types = set()
    committees = Committee.objects.filter(type="")
    for committee in committees:
        code = committee.committee_code
        chamber = committee.chamber
        if chamber == "S":
            chamber = "senate"
        elif chamber == "H":
            chamber = "house"
        else:
            chamber = "joint"
        url = f"https://api.congress.gov/v3/committee/{chamber}/{code}"
        params = {
            "api_key": API_KEY,
            "format": "json",
        }
        response = requests.get(url, params=params).json()["committee"]
        c_type = response["type"]
        committee.type = c_type
        committee_types.add(c_type)
        committee.save()
        time.sleep(0.5)
    print(f"Finished adding committee types: {committee_types}")


def get_house_committee_obj(name):
    committee_mapping = {
        "Taxation (Joint)": "jstx00",
        "Economic (Joint)": "jjec00",
        "Climate Crisis (select)": "hlcn00",
        "Modernization of Congress (select)": "hlmh00",
        "Printing (Joint)": "jspr00",
        "Library (Joint)": "jslc00",
        "Events Surrounding the 2012 Terrorist Attack on Benghazi (Select)": "hlzi00",
        "Deficit Reduction (Joint, Select)": "jsdf00",
        "Veterans Affairs": "hsvr00",
        "Argriculture": "hsag00",
        "Oversight and Reform": "hsgo00",
        "House Administration": "hsha00",
        "Intelligence (Select)": "hlig00",
        "Education and the Workforce": "hsed00",
        "Education and Labor": "hsed00",
        "Education and the Workplace": "hsed00",
    }
    if name in committee_mapping:
        committee_code = committee_mapping[name]
        return Committee.objects.get(committee_code=committee_code)
    try:
        normalized_name = f"{name} Committee"
        committee = Committee.objects.get(committee_name=normalized_name, chamber="H")
        return committee
    except:
        return None


def load_icpsr_bioguide_mapping(path):
    df = pd.read_csv(path, usecols=["icpsr", "bioguide_id"])
    df = df.dropna(subset=["icpsr", "bioguide_id"])
    return dict(zip(df["icpsr"].astype(int), df["bioguide_id"]))


def import_house_memberships():
    manual_mapping = {"Gonzalez-Colon": "G000582", "Christensen": "C000380"}
    created = 0
    skipped_member = 0
    skipped_term = 0
    skipped_committee = 0
    unmatched_committees = set()

    icpsr_map = load_icpsr_bioguide_mapping("./data/HSall_members.csv")

    df = pd.read_csv(
        "./data/house_membership.csv",
        usecols=["Congress", "ID #", "Name", "Committee Name"],
    )
    df = df.dropna(subset=["Congress", "ID #", "Name", "Committee Name"])

    for _, row in df.iterrows():
        congress_num = int(row["Congress"])
        icpsr_id = int(row["ID #"])

        bioguide = icpsr_map.get(icpsr_id)
        # try lookup by 1. Manual mapping 2. Last name 3. Last name and first name
        if not bioguide:
            last_name = row["Name"].split(",")[0]
            extended_first = row["Name"].split(",")[1]
            found = False
            if last_name in manual_mapping:
                bioguide = manual_mapping[last_name]
                found = True
            cands = CongressMember.objects.filter(last_name=last_name)
            if len(cands) == 1:
                bioguide = cands[0].bio_guide_id
                found = True
            else:
                for mem in cands:
                    if mem.first_name in extended_first:
                        bioguide = mem.bio_guide_id
                        found = True
                        break

            if not found:
                print(f"No bioguide mapping for ICPSR {icpsr_id} ({row['Name']})")
                skipped_member += 1
                continue

        try:
            member = CongressMember.objects.get(bio_guide_id=bioguide)
        except CongressMember.DoesNotExist:
            print(f"Member not in DB: {bioguide} ({row['Name']})")
            skipped_member += 1
            continue

        term = Term.objects.filter(
            member=member,
            congress_id=congress_num,
            chamber="H",
        ).first()

        if not term:
            print(f"Term not found: {row['Name']} congress {congress_num}")
            skipped_term += 1
            continue

        committee = get_house_committee_obj(row["Committee Name"])
        if not committee:
            print(f"Committee not found: {row['Committee Name']}")
            unmatched_committees.add(row["Committee Name"])
            skipped_committee += 1
            continue

        _, was_created = CommitteeMembership.objects.get_or_create(
            committee=committee,
            member_term=term,
            defaults={"role": ""},
        )

        if was_created:
            created += 1

    print(
        f"Created: {created}, Skipped (member): {skipped_member}, "
        f"Skipped (term): {skipped_term}, Skipped (committee): {skipped_committee}"
        f"Committee names not found: {unmatched_committees}"
    )


def get_senate_committee_obj(name):
    committee_mapping = {
        "Taxation (Joint)": "jstx00",
        "Economic (Joint)": "jjec00",
        "Printing (Joint)": "jspr00",
        "Library (Joint)": "jslc00",
        "Deficit Reduction (Joint, Select)": "jsdf00",
        "Indian Affairs (Select Committee)": "slia00",
        "Economic (Joint Committee)": "jjec00",
        "Intelligence (Select Committee)": "slin00",
        "Aging (Special Committee)": "spag00",
        "Ethics (Select Committee)": "slet00",
    }
    if name in committee_mapping:
        committee_code = committee_mapping[name]
        return Committee.objects.get(committee_code=committee_code)
    try:
        normalized_name = f"{name} Committee"
        committee = Committee.objects.get(committee_name=normalized_name, chamber="S")
        return committee
    except:
        return None


def import_senate_memberships():
    manual_mapping = {"Gonzalez-Colon": "G000582", "Christensen": "C000380"}
    created = 0
    skipped_member = 0
    skipped_term = 0
    skipped_committee = 0
    unmatched_committees = set()

    icpsr_map = load_icpsr_bioguide_mapping("./data/HSall_members.csv")

    df = pd.read_csv(
        "./data/senate_membership.csv",
        usecols=["Congress", "ID #", "Name", "Committee Name"],
    )
    df = df.dropna(subset=["Congress", "ID #", "Name", "Committee Name"])

    for _, row in df.iterrows():
        congress_num = int(row["Congress"])
        icpsr_id = int(row["ID #"])

        bioguide = icpsr_map.get(icpsr_id)
        # try lookup by 1. Manual mapping 2. Last name 3. Last name and first name
        if not bioguide:
            last_name = row["Name"].split(",")[0]
            extended_first = row["Name"].split(",")[1]
            found = False
            if last_name in manual_mapping:
                bioguide = manual_mapping[last_name]
                found = True
            cands = CongressMember.objects.filter(last_name=last_name)
            if len(cands) == 1:
                bioguide = cands[0].bio_guide_id
                found = True
            else:
                for mem in cands:
                    if mem.first_name in extended_first:
                        bioguide = mem.bio_guide_id
                        found = True
                        break

            if not found:
                print(f"No bioguide mapping for ICPSR {icpsr_id} ({row['Name']})")
                skipped_member += 1
                continue

        try:
            member = CongressMember.objects.get(bio_guide_id=bioguide)
        except CongressMember.DoesNotExist:
            print(f"Member not in DB: {bioguide} ({row['Name']})")
            skipped_member += 1
            continue

        term = Term.objects.filter(
            member=member,
            congress_id=congress_num,
            chamber="S",
        ).first()

        if not term:
            print(f"Term not found: {row['Name']} congress {congress_num}")
            skipped_term += 1
            continue

        committee = get_senate_committee_obj(row["Committee Name"])
        if not committee:
            print(f"Committee not found: {row['Committee Name']}")
            unmatched_committees.add(row["Committee Name"])
            skipped_committee += 1
            continue

        _, was_created = CommitteeMembership.objects.get_or_create(
            committee=committee,
            member_term=term,
            defaults={"role": ""},
        )

        if was_created:
            created += 1

    print(
        f"Created: {created}, Skipped (member): {skipped_member}, "
        f"Skipped (term): {skipped_term}, Skipped (committee): {skipped_committee}"
        f"Committee names not found: {unmatched_committees}"
    )


if __name__ == "__main__":
    # python get_committees.py
    get_committees()
    get_committee_types()
    import_house_memberships()
    import_senate_memberships()
