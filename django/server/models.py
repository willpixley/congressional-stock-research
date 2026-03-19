from django.db import models

# Choices

CHAMBER_CHOICES = {"H": "House of Representatives", "S": "Senate"}

PARTY_CHOICES = {"D": "Democrat", "R": "Republican", "I": "Independent"}


# Basically just biographical info
class CongressMember(models.Model):
    bio_guide_id = models.CharField(max_length=100, primary_key=True)
    first_name = models.CharField(max_length=255)
    middle_initial = models.CharField(max_length=2) # initial + .
    last_name = models.CharField(max_length=255)
    inverse_name = models.CharField(max_length=255, null=True) # Name in format last, first MI
    # Yes it is redundant, but gives more options to match how they are stored in most data sources
    full_name = models.CharField(max_length=255, null=True) 
   


class Congress(models.Model):
    congress_number = models.IntegerField(primary_key=True)
    start_year = models.DateField()
    end_year = models.DateField()

# Contains term-specific info
class Term(models.Model):
    congress = models.ForeignKey(Congress, on_delete=models.CASCADE)
    member = models.ForeignKey(CongressMember, on_delete=models.CASCADE)
    chamber = models.CharField(max_length=1, choices=CHAMBER_CHOICES)
    party = models.CharField(max_length=2)
    state = models.CharField(max_length=2)
    # There should only be one term for each member in a given congressional session and given chamber. 
    # Member should be able to move chambers
    class Meta:
        unique_together = ('member', 'congress', 'chamber')


class Sector(models.Model):
    sector_code = models.CharField(max_length=16, primary_key=True)
    sector_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)


class Committee(models.Model):
    committee_code = models.CharField(max_length=30, primary_key=True)
    committee_name = models.CharField(max_length=255)
    chamber = models.CharField(max_length=1, choices=CHAMBER_CHOICES)
    committee_members = models.ManyToManyField(
        Term, through="CommitteeMembership"
    )
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, default="00")


## Join table
class CommitteeMembership(models.Model):
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE)
    member_term = models.ForeignKey(Term, on_delete=models.CASCADE, null=True)
    role = models.CharField(max_length=100, default="")
    


## Join table
class CommitteeSector(models.Model):
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE)


class Stock(models.Model):
    ticker = models.CharField(max_length=9, primary_key=True)
    name = models.CharField(max_length=255, default=ticker)
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, null=True, blank=True)
    
    


class Trade(models.Model):
    ACTION_CHOICES = {
        "B": "Buy",
        "S": "Sell",
        "E": "Exchange"
    }
    type = models.CharField(max_length=1, choices=ACTION_CHOICES)
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    date = models.DateField()
    amount = models.IntegerField()
    member = models.ForeignKey(
        CongressMember,
        on_delete=models.CASCADE,
        to_field="bio_guide_id",  
        db_column="bio_guide_id",
        related_name="trade",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    flagged = models.BooleanField(default=False)
    checked = models.BooleanField(default=False)
    price_at_trade = models.DecimalField(default=0, decimal_places=2, max_digits=10)


### Tracks buy-sell pairs of similar quantities
### Must be: same member, stock, size, sell must happen after buy
class TradeSegment(models.Model):
    id = models.BigAutoField(primary_key=True)
    buy_trade = models.ForeignKey(
        Trade, on_delete=models.CASCADE, related_name="segments_as_buy"
    )
    sell_trade = models.ForeignKey(
        Trade,
        on_delete=models.CASCADE,
        related_name="segments_as_sell",
        null=True,
        blank=True,
    )

    closed = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.full_clean()  # calls clean() and field validation
        self.closed = self.sell_trade is not None
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.sell_trade is None:
            # No sell yet, nothing to validate
            return

        if self.buy_trade.member != self.sell_trade.member:
            raise ValidationError("Buy and sell must be by the same member.")
        if self.buy_trade.stock != self.sell_trade.stock:
            raise ValidationError("Buy and sell must be for the same stock.")
        if self.buy_trade.amount != self.sell_trade.amount:
            raise ValidationError("Buy and sell must be for the same amount.")
        if self.sell_trade.date <= self.buy_trade.date:
            raise ValidationError("Sell must happen after buy.")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["buy_trade"], name="unique_buy_trade_segment"
            )
        ]
