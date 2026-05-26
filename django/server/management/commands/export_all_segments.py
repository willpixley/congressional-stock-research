import csv
from datetime import date
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max
from server.models import TradeSegment, Term

FALLBACK_END_DATE = date(2025, 12, 31)


class Command(BaseCommand):
    help = "Export all trade segments to CSV (synthetic sell date for open segments)"

    @transaction.atomic
    def handle(self, *args, **options):
        filename = "./data/trade_segments.csv"

        fields = [
            "segment_id",
            "closed",
            "synthetic_sell",
            "buy_trade_id",
            "buy_date",
            "buy_amount",
            "buy_price",
            "buy_disclosure_date",
            "buy_conflicted",
            "sell_trade_id",
            "sell_date",
            "sell_amount",
            "sell_price",
            "sell_disclosure_date",
            "sell_conflicted",
            "member_bio_guide_id",
            "member_name",
            "party",
            "state",
            "chamber",
            "stock_ticker",
            "stock_name",
            "sector_code",
            "sector_name",
        ]

        # Precompute final-term end dates per member (one query)
        final_term_ends = dict(
            Term.objects.values_list("member_id").annotate(
                last_end=Max("congress__end_year")
            )
        )

        capped_no_terms = 0
        capped_still_in_office = 0
        exported = 0

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fields)

            segments = TradeSegment.objects.select_related(
                "buy_trade__member",
                "buy_trade__stock__sector",
                "sell_trade",
            )

            for segment in segments.iterator(chunk_size=1000):
                buy = segment.buy_trade
                sell = segment.sell_trade
                member = buy.member
                stock = buy.stock
                sector = stock.sector if stock else None

                # Resolve sell-side values
                if sell is not None:
                    sell_id = sell.id
                    sell_date = sell.date
                    sell_amount = sell.amount
                    sell_price = sell.price_at_trade
                    sell_disclosure = sell.disclosure_date
                    sell_conflicted = sell.conflicted
                    synthetic = False
                else:
                    final_end = final_term_ends.get(member.bio_guide_id)
                    if final_end is None:
                        final_end = FALLBACK_END_DATE
                        capped_no_terms += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"Segment {segment.id}: member "
                                f"{member.bio_guide_id} has no terms, "
                                f"using fallback {FALLBACK_END_DATE}"
                            )
                        )
                    elif final_end > FALLBACK_END_DATE:
                        final_end = FALLBACK_END_DATE
                        capped_still_in_office += 1

                    sell_id = None
                    sell_date = final_end
                    sell_amount = buy.amount
                    sell_price = None
                    sell_disclosure = None
                    sell_conflicted = None
                    synthetic = True

                # Term lookup for the buy date (for party/state/chamber)
                term = Term.objects.filter(
                    member=member,
                    congress__start_year__lte=buy.date,
                    congress__end_year__gte=buy.date,
                ).first()

                writer.writerow(
                    [
                        segment.id,
                        segment.closed,
                        synthetic,
                        buy.id,
                        buy.date,
                        buy.amount,
                        buy.price_at_trade,
                        buy.disclosure_date,
                        buy.conflicted,
                        sell_id,
                        sell_date,
                        sell_amount,
                        sell_price,
                        sell_disclosure,
                        sell_conflicted,
                        member.bio_guide_id,
                        member.full_name,
                        term.party if term else None,
                        term.state if term else None,
                        term.get_chamber_display() if term else None,
                        stock.ticker,
                        stock.name,
                        sector.sector_code if sector else None,
                        sector.sector_name if sector else None,
                    ]
                )
                exported += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {exported} segments to {filename} "
                f"(capped {capped_still_in_office} still-in-office, "
                f"{capped_no_terms} no-terms at {FALLBACK_END_DATE})"
            )
        )
