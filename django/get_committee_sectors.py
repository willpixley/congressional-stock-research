import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from server.models import Committee, Sector, CommitteeSector


# Does not include all committees (like the state of the union committee)
HOUSE_COMMITTEE_SECTORS = {
    "hsgo00": [
        "92",
        "56",
    ],  # Oversight and Government Reform: public admin and admin support
    "hsju00": [
        "92",
        "81",
    ],  # Judiciary - public admin and other services. Other servies includes things like grants and advocacy
    "hsed00": [
        "61",
        "62",
        "81",
    ],  # Education and Workforce -> Education, Health Care/social assistance, other services
    "hotl00": ["92"],  # Tom Lantos Human Rights Commission -> Public Admin
    "hspw00": [
        "23",
        "48",
        "49",
    ],  # Transportation and Infrastructure ->  construction and transportation
    "hsba00": [
        "52",
        "53",
        "55",
    ],  # Financial Services -> Finance, Real Estate, Managemt of companies and enterprises
    "hsag00": [
        "11",
        "42",
        "72",
        "31",
    ],  # Agriculture -> Agriculture, Wholesale Trade, food services, food manufacturing
    "hsso00": ["92"],  # Ethics -> Public Admin
    "hssm00": [
        "44",
        "45",
        "54",
        "81",
    ],  # Small Business -> Retail, Professional Services, other services (includes things like dry cleaning and other small businesses)
    "hsap00": ["92"],  # Appropriations -> Public Admin
    "hsfa00": [
        "92",
        "21",
        "33",
    ],  # Foreign Affairs -> Public Admin, mining, quarrying, oil and gas, aerospace and defense manufacturing
    "hsas00": [
        "33",
        "54",
    ],  # Armed Services -> Manufacturing (defense), professional, scientific, and technical services
    "hsii00": ["11", "21", "22"],  # Natural Resources -> Agriculture, Mining, Utilities
    "hlig00": ["92", "54"],  # Intelligence -> Public Admin, Professional/Technical
    "hswm00": ["52", "92"],  # Ways and Means -> Finance, Public Admin
    "hssy00": [
        "54",
        "51",
        "33",
    ],  # Science, Space, and Technology -> Professional/technical, Information, Aerospace Manufacturing
    "hsvr00": ["92", "62"],  # Veterans Affairs -> Public Admin, Health Care
    "hsha00": ["92"],  # House Administration -> Public Admin
    "hshm00": [
        "92",
        "56",
        "33",
    ],  # Homeland Security -> Public Admin, Admin Support, Defense manufacturing
    "hsif00": [
        "22",
        "51",
        "54",
        "45",
        "11",
        "21",
    ],  # Energy and Commerce -> Utilities, Information, Professional, retail trade (personal items) (consumer protections), agriculture, mining and extraction
    "hsru00": ["92"],  # Rules -> Public Admin
    "hsbu00": ["92", "52"],  # Budget -> Public Admin, Finance
    "hlie00": ["62"],  # Select Panel -> Health Care (was focused on Planned Parenthood)
    "hlmh00": ["92"],  # Modernization of Congress -> Public Admin
    "hlcn00": [
        "22",
        "21",
        "11",
        "32",
        "48",
    ],  # Climate Crisis -> Utilities, Mining, Agriculture, chemical and plastics manufacturing, transporation
    "hlef00": [
        "52",
        "92",
        "62",
    ],  # Economic Disparity -> Finance, Public Adminm, Social Assistance
    "hlzs00": [
        "51",
        "33",
        "54",
        "32",
    ],  # China Competition -> Information, Manufacturing, Professional, Manufacturing again
}


SENATE_COMMITTEE_SECTORS = {
    "sseg00": [
        "21",
        "22",
        "11",
    ],  # Energy and Natural Resources -> Mining, Utilities, Agriculture
    "ssva00": ["92", "62"],  # Veterans Affairs -> Public Admin, Health Care
    "ssra00": ["92"],  # Rules and Administration -> Public Admin
    "sssb00": [
        "44",
        "45",
        "54",
        "81",
    ],  # Small Business -> Retail, Professional Services
    "ssju00": ["92", "81"],  # Judiciary -> Public Admin, Other Services
    "sshr00": [
        "61",
        "62",
        "81",
        "52",
    ],  # Health, Education, Labor, Pensions -> Education, Health Care, Other Services. Finance and insurance
    "ssga00": [
        "92",
        "56",
        "33",
    ],  # Homeland Security and Governmental Affairs -> Public Admin, Admin Support, Defense
    "ssfr00": ["92", "33"],  # Foreign Relations -> Public Admin, defense manufacturing
    "ssfi00": ["52", "92"],  # Finance -> Finance, Public Admin
    "ssev00": [
        "22",
        "21",
        "11",
        "48",
    ],  # Environment and Public Works -> Utilities, Mining, Agriculture, transportation
    "ssbu00": ["92", "52"],  # Budget -> Public Admin, Finance
    "sscm00": [
        "51",
        "48",
        "49",
        "54",
        "44",
        "45",
    ],  # Commerce, Science, Transportation -> Information, Transportation, Professional
    "ssbk00": ["52", "53"],  # Banking, Housing, Urban Affairs -> Finance, Real Estate
    "ssap00": ["92"],  # Appropriations -> Public Admin
    "ssas00": ["33", "54"],  # Armed Services -> Manufacturing, Professional/Technical
    "slin00": [
        "92",
        "54",
        "33",
    ],  # Intelligence -> Public Admin, Professional/Technical, Defense
    "spag00": ["62", "92"],  # Aging -> Health Care, Public Admin
    "ssaf00": [
        "11",
        "42",
        "72",
        "31",
    ],  # Agriculture, Nutrition, Forestry -> Agriculture, Wholesale Trade
    "slet00": ["92"],  # Ethics -> Public Admin
    "scnc00": ["92"],  # Narcotics Control Caucus -> Public Admin
    "slia00": ["11", "92"],  # Indian Affairs -> Agriculture, Public Admin
    "sowg00": [
        "92",
        "33",
    ],  # National Security Working Group -> Public Admin, Manufacturing
}

JOINT_COMMITTEE_SECTORS = {
    "jcpk00": [
        "51",
        "33",
        "54",
    ],  # China Commission -> Information, Manufacturing, Professional
    "jstx00": ["52", "92"],  # Taxation -> Finance, Public Admin
    "jslc00": ["71"],  # Library -> Arts/Entertainment?
    "jcse00": ["33"],  # Helsinki Commission -> Defense spending
    "jsec00": ["52", "92"],  # Economic Committee -> Finance, Public Admin
    "jsdf00": ["92", "52"],  # Deficit Reduction -> Public Admin, Finance
    "jcuc00": [
        "51",
        "33",
        "54",
    ],  # US-China Security Review -> Information, Manufacturing, Professional
    "jocp00": ["92", "52"],  # Congressional Oversight Panel -> Public Admin, Finance
    "jcov00": [
        "92",
        "52",
    ],  # Congressional Oversight Commission -> Public Admin, Finance
    "jjec00": ["52", "92"],  # Joint Economic Committee -> Finance, Public Admin
    "jhje00": ["52", "92"],  # Joint Economic Committee -> Finance, Public Admin
}


def import_committee_sectors():
    created = 0
    skipped_committee = 0
    skipped_sector = 0

    all_mappings = {
        **HOUSE_COMMITTEE_SECTORS,
        **SENATE_COMMITTEE_SECTORS,
        **JOINT_COMMITTEE_SECTORS,
    }

    for committee_code, sector_codes in all_mappings.items():
        try:
            committee = Committee.objects.get(committee_code=committee_code)
        except Committee.DoesNotExist:
            print(f"Committee not found: {committee_code}")
            skipped_committee += 1
            continue

        for sector_code in sector_codes:
            try:
                sector = Sector.objects.get(sector_code=sector_code)
            except Sector.DoesNotExist:
                print(f"Sector not found: {sector_code} for committee {committee_code}")
                skipped_sector += 1
                continue

            _, was_created = CommitteeSector.objects.get_or_create(
                committee=committee,
                sector=sector,
            )

            if was_created:
                created += 1

    print(
        f"Created: {created}, Skipped (committee): {skipped_committee}, Skipped (sector): {skipped_sector}"
    )


if __name__ == "__main__":
    import_committee_sectors()
