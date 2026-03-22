import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from server.models import TradeSegment, Term


class Command(BaseCommand):
    help = "Export all closed trade segments to CSV"

    @transaction.atomic
    def handle(self, *args, **options):
        filename = "./output/closed_trade_segments.csv"

        fields = [
            "segment_id",
            "closed",
            "buy_trade_id",
            "buy_date",
            "buy_amount",
            "buy_price",
            "sell_trade_id",
            "sell_date",
            "sell_amount",
            "sell_price",
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

                term = Term.objects.filter(
                    member=member,
                    congress__start_year__lte=buy.date,
                    congress__end_year__gte=buy.date,
                ).first()

                party = term.party if term else None
                state = term.state if term else None
                chamber = term.get_chamber_display() if term else None

                writer.writerow([
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
                    party,
                    state,
                    chamber,
                    stock.ticker,
                    stock.name,
                    sector.sector_code if sector else None,
                    sector.sector_name if sector else None,
                ])

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported closed trade segments to {filename}"
            )
        )