import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from server.models import TradeSegment


class Command(BaseCommand):
    help = "Export all closed trade segments to CSV"

    @transaction.atomic
    def handle(self, *args, **options):
        filename = "closed_trade_segments.csv"

        fields = [
            # Segment
            "segment_id",
            "closed",
            # Buy trade
            "buy_trade_id",
            "buy_date",
            "buy_amount",
            "buy_price",
            # Sell trade
            "sell_trade_id",
            "sell_date",
            "sell_amount",
            "sell_price",
            # Member
            "member_bio_guide_id",
            "member_name",
            "member_party",
            "member_state",
            "member_chamber",
            # Stock / sector
            "stock_ticker",
            "stock_name",
            "sector_code",
            "sector_name",
        ]

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fields)

            segments = TradeSegment.objects.filter(
                closed=True, sell_trade__isnull=False
            ).select_related(
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

                writer.writerow(
                    [
                        segment.id,
                        segment.closed,
                        buy.id,
                        buy.date,
                        buy.amount,
                        buy.price_at_trade,
                        sell.id,
                        sell.date,
                        sell.amount,
                        sell.price_at_trade,
                        member.bio_guide_id,
                        member.full_name,
                        member.get_party_display(),
                        member.state,
                        member.get_chamber_display(),
                        stock.ticker,
                        stock.name,
                        sector.sector_code if sector else None,
                        sector.sector_name if sector else None,
                    ]
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {segments.count()} closed trade segments to {filename}"
            )
        )
