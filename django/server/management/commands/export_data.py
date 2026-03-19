import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from server.models import Trade


class Command(BaseCommand):
    help = "Export joined trade/member/stock/sector/committee data to CSV"

    @transaction.atomic
    def handle(self, *args, **options):
        filename = "joined_data.csv"
        fields = [
            "trade_id",
            "trade_date",
            "action",
            "amount",
            "flagged",
            "price_at_trade",
            "current_price",
            "member_name",
            "member_party",
            "member_state",
            "member_chamber",
            "stock_ticker",
            "stock_name",
            "sector_code",
            "sector_name",
            "committee_names",
            "member_bio_guide_id",
        ]

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fields)

            # Prefetch related data to minimize queries
            trades = Trade.objects.select_related(
                "member", "stock__sector"
            ).prefetch_related("member__committeemembership_set__committee")

            for trade in trades.iterator(chunk_size=2000):
                member = trade.member
                stock = trade.stock
                sector = stock.sector if stock else None

                committees = [
                    m.committee.committee_name
                    for m in member.committeemembership_set.all()
                ]
                committee_names = ", ".join(committees) if committees else ""

                writer.writerow(
                    [
                        trade.id,
                        trade.date,
                        trade.get_type_display(),
                        trade.amount,
                        trade.flagged,
                        trade.price_at_trade,
                        trade.current_price,
                        member.full_name,
                        member.get_party_display(),
                        member.state,
                        member.get_chamber_display(),
                        stock.ticker,
                        stock.name,
                        sector.sector_code if sector else None,
                        sector.sector_name if sector else None,
                        committee_names,
                        member.bio_guide_id,
                    ]
                )

        self.stdout.write(
            self.style.SUCCESS(f"Exported {Trade.objects.count()} trades to {filename}")
        )
