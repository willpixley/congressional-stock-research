# detect_conflicts.py
import os
import json
import django
import numpy as np
from collections import defaultdict

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
django.setup()

from django.db.models import Q
from server.models import (
    TradeSegment,
    Trade,
    Hearing,
    Congress,
    Stock,
    CommitteeMembership,
    Term,
)

SD_THRESHOLD = 2.5
OUTPUT_PATH = "conflicts.json"


def cos_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity. a: (d,), b: (n, d). Returns (n,)."""
    a_n = a / np.linalg.norm(a)
    b_n = b / np.linalg.norm(b, axis=1, keepdims=True)
    return b_n @ a_n


def find_congress_for_date(date) -> Congress | None:
    return Congress.objects.filter(start_year__lte=date, end_year__gte=date).first()


def run():

    Trade.objects.update(conflicted=False)
    print("All trades reset")
    print("Loading hearings...")
    hearings_by_congress: dict[int, list[dict]] = defaultdict(list)
    hearings_qs = Hearing.objects.filter(embedding__isnull=False).prefetch_related(
        "committees"
    )
    for h in hearings_qs:
        committee_codes = list(h.committees.values_list("committee_code", flat=True))
        hearings_by_congress[h.congress_id].append(
            {
                "jacket_no": h.jacket_no,
                "embedding": np.array(h.embedding),
                "committee_codes": committee_codes,
                "chamber": h.chamber,
                "congress": h.congress_id,
            }
        )
    print(
        f"  {sum(len(v) for v in hearings_by_congress.values())} hearings across {len(hearings_by_congress)} congresses"
    )

    # Precompute per-hearing similarity distribution across ALL stocks with embeddings
    print("Computing per-hearing similarity distributions...")
    stocks_with_emb = list(
        Stock.objects.filter(embedding__isnull=False).exclude(description="")
    )
    stock_emb_matrix = np.array([s.embedding for s in stocks_with_emb])
    stock_emb_matrix = stock_emb_matrix / np.linalg.norm(
        stock_emb_matrix, axis=1, keepdims=True
    )

    hearing_stats: dict[str, tuple[float, float]] = {}  # jacket_no -> (mean, std)
    for cn, hearings in hearings_by_congress.items():
        for h in hearings:
            sims = cos_sim(h["embedding"], stock_emb_matrix)
            hearing_stats[h["jacket_no"]] = (float(sims.mean()), float(sims.std()))
    print(f"  computed stats for {len(hearing_stats)} hearings")

    # Iterate trade segments
    print("Scanning trade segments...")
    segments = TradeSegment.objects.select_related(
        "buy_trade__stock", "buy_trade__member", "sell_trade"
    ).filter(buy_trade__stock__embedding__isnull=False)

    results = []
    flagged_trade_ids = set()
    total = segments.count()

    for i, seg in enumerate(segments.iterator()):
        buy = seg.buy_trade
        stock = buy.stock
        member = buy.member
        trade_date = buy.date

        congress = find_congress_for_date(trade_date)
        if congress is None:
            continue

        # Committees this member sat on this congress
        member_committee_codes = set(
            CommitteeMembership.objects.filter(
                member_term__member=member, member_term__congress=congress
            ).values_list("committee__committee_code", flat=True)
        )
        if not member_committee_codes:
            continue

        # Candidate hearings: same congress + at least one shared committee
        candidates = [
            h
            for h in hearings_by_congress.get(congress.congress_number, [])
            if member_committee_codes.intersection(h["committee_codes"])
        ]
        if not candidates:
            continue

        stock_emb = np.array(stock.embedding)
        stock_emb_norm = stock_emb / np.linalg.norm(stock_emb)

        matches = []
        for h in candidates:
            h_emb_norm = h["embedding"] / np.linalg.norm(h["embedding"])
            sim = float(stock_emb_norm @ h_emb_norm)
            mu, sigma = hearing_stats[h["jacket_no"]]
            if sigma == 0:
                continue
            z = (sim - mu) / sigma
            if z > SD_THRESHOLD:
                shared = list(member_committee_codes.intersection(h["committee_codes"]))
                matches.append(
                    {
                        "hearing_jacket_no": h["jacket_no"],
                        "chamber": h["chamber"],
                        "congress": h["congress"],
                        "committee_codes": shared,
                        "similarity": round(sim, 4),
                        "z_score": round(z, 3),
                        "hearing_mean": round(mu, 4),
                        "hearing_std": round(sigma, 4),
                    }
                )

        if matches:
            results.append(
                {
                    "segment_id": seg.id,
                    "buy_trade_id": buy.id,
                    "sell_trade_id": seg.sell_trade_id,
                    "member": member.full_name
                    or f"{member.first_name} {member.last_name}",
                    "stock": stock.ticker,
                    "buy_date": str(buy.date),
                    "congress": congress.congress_number,
                    "matches": sorted(matches, key=lambda m: -m["z_score"]),
                }
            )
            flagged_trade_ids.add(buy.id)
            if seg.sell_trade_id:
                flagged_trade_ids.add(seg.sell_trade_id)

        if (i + 1) % 500 == 0:
            print(f"  {i + 1}/{total}  flagged: {len(results)}")

    # Persist
    print(f"\nUpdating {len(flagged_trade_ids)} trades as conflicted...")
    Trade.objects.filter(id__in=flagged_trade_ids).update(conflicted=True)

    print(f"Writing {len(results)} flagged segments to {OUTPUT_PATH}")
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    run()
