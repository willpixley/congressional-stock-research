import os
import django
import requests
from dotenv import load_dotenv
import time


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

load_dotenv()

API_KEY = os.environ.get("CONGRESS_API_KEY")


django.setup()
from server.models import Committee


def getCommittees():
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

                if "parent" not in committee:
                    committee_objs.append(
                        Committee(
                            committee_code=id,
                            committee_name=name,
                            chamber=chamber,
                            parent=None,
                        )
                    )
                else:
                    parent = committee["parent"]
                    parent_obj, _ = Committee.objects.get_or_create(
                        committee_code=parent["systemCode"],
                        defaults={
                            "committee_name": parent["name"],
                            "chamber": chamber,
                            "parent": None,
                        },
                    )
                    committee_objs.append(
                        Committee(
                            committee_code=id,
                            committee_name=name,
                            chamber=chamber,
                            parent=parent_obj,
                        )
                    )

    created = Committee.objects.bulk_create(committee_objs, ignore_conflicts=True)
    print(f"{len(created)} committees created.")


# Will take about 20 minutes to run. Must call the /committee/chamber/code API to get committee type (standing, joint, etc.)
def getCommitteeTypes():
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


if __name__ == "__main__":
    # python get_committees.py
    getCommittees()
    getCommitteeTypes()
