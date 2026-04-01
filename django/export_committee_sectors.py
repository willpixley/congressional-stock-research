import os
import django
from collections import defaultdict

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from server.models import Committee, Sector, CommitteeSector

qs = CommitteeSector.objects.select_related("committee", "sector").order_by(
    "committee__committee_name", "sector__sector_name"
)

grouped = defaultdict(lambda: {"name": "", "sectors": []})

for cs in qs:
    grouped[cs.committee.committee_code]["name"] = cs.committee.committee_name
    grouped[cs.committee.committee_code]["sectors"].append(cs.sector.sector_name)

print("| Committee | Sectors |")
print("|-----------|---------|")

for code, data in grouped.items():
    sectors = ", ".join(data["sectors"])
    print(f"| {data['name']} | {sectors} |")
