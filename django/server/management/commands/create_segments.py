from django.core.management.base import BaseCommand
from django.db import transaction
from server.models import Trade, TradeSegment
from collections import defaultdict


class Command(BaseCommand):
    help = "Create or update TradeSegments from existing trades"

    def handle(self, *args, **kwargs):
        trades = Trade.objects.order_by("member_id", "stock_id", "date", "id")

        segments_to_create = []
        segments_to_update = []

        member_trades = defaultdict(list)
        for t in trades:
            member_trades[t.member_id].append(t)

        open_segments_by_member = defaultdict(list)
        open_segments = TradeSegment.objects.filter(
            closed=False, sell_trade__isnull=True
        ).select_related("buy_trade")

        for seg in open_segments:
            open_segments_by_member[seg.buy_trade.member_id].append(seg)

        for member_id, tlist in member_trades.items():
            buys = [t for t in tlist if t.type == "B"]
            sells = [t for t in tlist if t.type == "S"]

            # Index sells by (stock, amount)
            sells_by_key = defaultdict(list)
            for s in sells:
                sells_by_key[(s.stock_id, s.amount)].append(s)

            used_sells = set()
            matched_open_buys = set()

            # close existing segs
            for seg in open_segments_by_member.get(member_id, []):
                buy = seg.buy_trade
                candidates = sells_by_key.get((buy.stock_id, buy.amount), [])

                matching_sell = next(
                    (
                        s
                        for s in candidates
                        if s.date > buy.date and s.id not in used_sells
                    ),
                    None,
                )

                if matching_sell:
                    seg.sell_trade = matching_sell
                    seg.closed = True
                    segments_to_update.append(seg)
                    used_sells.add(matching_sell.id)
                    matched_open_buys.add(buy.id)

            # create new segments for unmatched buys
            for buy in buys:
                if buy.id in matched_open_buys:
                    continue

                candidates = sells_by_key.get((buy.stock_id, buy.amount), [])
                matching_sell = next(
                    (
                        s
                        for s in candidates
                        if s.date > buy.date and s.id not in used_sells
                    ),
                    None,
                )

                segments_to_create.append(
                    TradeSegment(
                        buy_trade=buy,
                        sell_trade=matching_sell,
                        closed=matching_sell is not None,
                    )
                )

                if matching_sell:
                    used_sells.add(matching_sell.id)

        with transaction.atomic():
            if segments_to_create:
                TradeSegment.objects.bulk_create(
                    segments_to_create, ignore_conflicts=True
                )

            if segments_to_update:
                TradeSegment.objects.bulk_update(
                    segments_to_update, ["sell_trade", "closed"]
                )

        total = len(segments_to_create) + len(segments_to_update)
        self.stdout.write(
            self.style.SUCCESS(f"Processed {total} trade segments (created + updated).")
        )
