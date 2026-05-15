from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

CURRENCIES = [
    ('USD', 'USD — US Dollar'),
    ('EUR', 'EUR — Euro'),
    ('GBP', 'GBP — British Pound'),
    ('JPY', 'JPY — Japanese Yen'),
    ('CHF', 'CHF — Swiss Franc'),
    ('ZAR', 'ZAR — South African Rand'),
]

FOREX_PAIRS = [
    ('EURUSD', 'EUR/USD'),
    ('GBPUSD', 'GBP/USD'),
    ('USDJPY', 'USD/JPY'),
    ('USDCHF', 'USD/CHF'),
    ('AUDUSD', 'AUD/USD'),
    ('USDCAD', 'USD/CAD'),
    ('NZDUSD', 'NZD/USD'),
    ('EURGBP', 'EUR/GBP'),
]


class UserProfile(models.Model):
    user             = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    currency         = models.CharField(max_length=3, choices=CURRENCIES, default='USD')
    starting_balance = models.FloatField(default=0.0)
    initialized      = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s profile"


class Broker(models.Model):
    user    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='brokers')
    name    = models.CharField(max_length=100)
    spread  = models.FloatField(default=1.0)
    wins    = models.IntegerField(default=0)
    losses  = models.IntegerField(default=0)

    def win_rate(self):
        t = self.wins + self.losses
        return round(self.wins / t * 100, 1) if t > 0 else None

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class Investor(models.Model):
    user    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investors')
    name    = models.CharField(max_length=100)
    wins    = models.IntegerField(default=0)
    losses  = models.IntegerField(default=0)
    net_pl  = models.FloatField(default=0.0)

    def win_rate(self):
        t = self.wins + self.losses
        return round(self.wins / t * 100, 1) if t > 0 else None


class Trade(models.Model):
    TRADE_TYPES = [('STOCK', 'Stock'), ('FOREX', 'Forex')]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades')
    trade_type = models.CharField(max_length=10, choices=TRADE_TYPES, default='STOCK')

    # ── Stock fields ──────────────────────────────────────────
    symbol            = models.CharField(max_length=20, blank=True, default='')
    shares            = models.IntegerField(default=0)
    entry_price_share = models.FloatField(default=0.0)
    exit_price_share  = models.FloatField(default=0.0)
    profit_per_share  = models.FloatField(default=0.0)

    # ── Forex fields ──────────────────────────────────────────
    pair        = models.CharField(max_length=10, blank=True, default='')
    direction   = models.CharField(max_length=4, blank=True, default='')  # BUY / SELL
    lot_size    = models.FloatField(default=0.0)
    entry_price = models.FloatField(default=0.0)
    exit_price  = models.FloatField(default=0.0)
    pips        = models.FloatField(default=0.0)

    # ── Common ────────────────────────────────────────────────
    total_profit   = models.FloatField(default=0.0)
    balance_after  = models.FloatField(default=0.0)
    broker         = models.CharField(max_length=100, blank=True)
    investor       = models.CharField(max_length=100, blank=True)
    notes          = models.TextField(blank=True)
    screenshot_b64 = models.TextField(blank=True, default='')  # base64 image
    rating         = models.IntegerField(default=0)            # 1-5 stars, 0 = unrated
    locked         = models.BooleanField(default=False)
    created_at     = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['id']

    def __str__(self):
        asset = self.symbol if self.trade_type == 'STOCK' else self.pair
        return f"{self.trade_type} {asset} #{self.id} ({self.user.username})"


class TokenWallet(models.Model):
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    tokens        = models.IntegerField(default=10)
    total_earned  = models.IntegerField(default=10)
    total_used    = models.IntegerField(default=0)


class TokenHistory(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='token_history')
    action     = models.CharField(max_length=200)
    change     = models.IntegerField()
    balance    = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ChatMessage(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    message    = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering  = ['created_at']
        indexes   = [models.Index(fields=['created_at'])]

    def __str__(self):
        return f"{self.user.username}: {self.message[:60]}"
