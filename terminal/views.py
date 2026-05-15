import json, random, string, time
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import (UserProfile, Broker, Investor, Trade,
                     TokenWallet, TokenHistory, ChatMessage)

GIFT_CODE         = 'IAMADMIN34'
DEFAULT_BROKERS   = []
DEFAULT_INVESTORS = []
CHAT_RATE_LIMIT   = 3   # seconds between messages per user
CHAT_MAX_LEN      = 500
CHAT_FETCH_LIMIT  = 80  # messages per fetch


# ══════════════════════════════════════════════════════════════
#  ads.txt
# ══════════════════════════════════════════════════════════════

def ads_txt(request):
    return HttpResponse(
        "google.com, pub-2199279982019872, DIRECT, f08c47fec0942fa0",
        content_type="text/plain"
    )


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def get_profile(user):
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        for name, spread in DEFAULT_BROKERS:
            Broker.objects.create(user=user, name=name, spread=spread)
        for name in DEFAULT_INVESTORS:
            Investor.objects.create(user=user, name=name)
    TokenWallet.objects.get_or_create(user=user)
    return profile


def recalc(user):
    running = user.profile.starting_balance
    for t in user.trades.order_by('id'):
        running = round(running + t.total_profit, 2)
        t.balance_after = running
        t.save(update_fields=['balance_after'])


def deduct_tok(user, n, reason):
    w = user.wallet
    w.tokens     = max(0, w.tokens - n)
    w.total_used += n
    w.save()
    TokenHistory.objects.create(user=user, action=reason, change=-n, balance=w.tokens)


def add_tok(user, n, reason):
    w = user.wallet
    w.tokens       += n
    w.total_earned += n
    w.save()
    TokenHistory.objects.create(user=user, action=reason, change=+n, balance=w.tokens)
    return w.tokens


def bump_stats(user, trade):
    win = trade.total_profit > 0
    try:
        b = user.brokers.get(name=trade.broker)
        if win: b.wins   += 1
        else:   b.losses += 1
        b.save()
    except Broker.DoesNotExist:
        pass
    try:
        iv = user.investors.get(name=trade.investor)
        if win: iv.wins   += 1
        else:   iv.losses += 1
        iv.net_pl = round(iv.net_pl + trade.total_profit, 2)
        iv.save()
    except Investor.DoesNotExist:
        pass


def ok(d, status=200):  return JsonResponse(d, status=status)
def err(m, status=400): return JsonResponse({'error': m}, status=status)


def trade_to_dict(t):
    return {
        'id': t.id, 'trade_type': t.trade_type,
        # stock
        'symbol': t.symbol, 'shares': t.shares,
        'entry_price_share': t.entry_price_share,
        'exit_price_share':  t.exit_price_share,
        'profit_per_share':  t.profit_per_share,
        # forex
        'pair': t.pair, 'direction': t.direction,
        'lot_size': t.lot_size, 'entry_price': t.entry_price,
        'exit_price': t.exit_price, 'pips': t.pips,
        # common
        'total_profit': t.total_profit, 'balance_after': t.balance_after,
        'broker': t.broker, 'investor': t.investor,
        'notes': t.notes, 'rating': t.rating, 'locked': t.locked,
        'has_screenshot': bool(t.screenshot_b64),
        'created_at': t.created_at.strftime('%Y-%m-%d %H:%M'),
    }


# ══════════════════════════════════════════════════════════════
#  PAGES
# ══════════════════════════════════════════════════════════════

def home_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'terminal/home.html')


def logout_view(request):
    """Custom logout that clears social auth session and redirects to home."""
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    return redirect('/')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        email = request.POST.get('email', '').strip().lower()
        email_error = None
        if not email:
            email_error = 'Email address is required.'
        elif '@' not in email:
            email_error = 'Enter a valid email address.'
        elif User.objects.filter(email__iexact=email).exists():
            email_error = 'An account with this email already exists. Please sign in.'
        if email_error:
            return render(request, 'registration/register.html',
                          {'form': form, 'email_error': email_error, 'email_val': email})
        if form.is_valid():
            user = form.save(commit=False)
            user.email = email
            user.save()
            get_profile(user)
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
@ensure_csrf_cookie
def dashboard_view(request):
    get_profile(request.user)
    return render(request, 'terminal/dashboard.html',
                  {'username': request.user.username})


# ══════════════════════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════════════════════

@login_required
@csrf_exempt
def api_setup(request):
    profile = get_profile(request.user)
    if request.method == 'GET':
        return ok({'initialized': profile.initialized,
                   'starting_balance': profile.starting_balance,
                   'currency': profile.currency})
    if request.method == 'POST':
        try:
            d   = json.loads(request.body)
            bal = float(d.get('starting_balance', 0))
            cur = d.get('currency', 'USD')
            if bal < 0: return err('Balance cannot be negative.')
        except:
            return err('Invalid data.')
        profile.starting_balance = round(bal, 2)
        profile.currency         = cur
        profile.initialized      = True
        profile.save()
        recalc(request.user)
        return ok({'success': True})
    return err('Method not allowed.', 405)


# ══════════════════════════════════════════════════════════════
#  TRADES — LIST
# ══════════════════════════════════════════════════════════════

@login_required
def api_trades_list(request):
    if request.method != 'GET':
        return err('Method not allowed.', 405)
    trades = [trade_to_dict(t) for t in request.user.trades.order_by('id')]
    return ok({'trades': trades})


# ══════════════════════════════════════════════════════════════
#  TRADES — CREATE STOCK
# ══════════════════════════════════════════════════════════════

@login_required
@csrf_exempt
def api_trades_create(request):
    if request.method != 'POST': return err('Method not allowed.', 405)
    user = request.user
    try: d = json.loads(request.body)
    except: return err('Invalid body.')

    symbol = d.get('symbol', '').strip().upper()
    if not symbol or not symbol.isalpha(): return err('Symbol must be letters only.')

    try:
        shares = int(d.get('shares', 0))
        if shares <= 0: raise ValueError()
    except: return err('Shares must be > 0.')

    try:
        entry = float(d.get('entry_price_share', 0))
        exit_ = float(d.get('exit_price_share',  0))
        if entry <= 0 or exit_ <= 0: raise ValueError()
    except: return err('Prices must be positive.')

    if d.get('calc_mode') == 'custom':
        try: pps = float(d.get('profit_per_share', 0))
        except: return err('Invalid profit per share.')
    else:
        pps = round(exit_ - entry, 4)

    total    = round(shares * pps, 2)
    broker   = d.get('broker',   '').strip()
    investor = d.get('investor', '').strip()
    notes    = d.get('notes',    '').strip()

    try: mult = max(1, min(100, int(d.get('multiplier', 1))))
    except: mult = 1

    wallet = user.wallet
    if wallet.tokens < mult:
        return ok({'token_error': True, 'tokens_available': wallet.tokens,
                   'tokens_needed': mult}, status=402)

    ids = []
    for _ in range(mult):
        t = Trade.objects.create(
            user=user, trade_type='STOCK', symbol=symbol, shares=shares,
            entry_price_share=round(entry,4), exit_price_share=round(exit_,4),
            profit_per_share=round(pps,4), total_profit=total,
            broker=broker, investor=investor, notes=notes)
        bump_stats(user, t)
        ids.append(t.id)

    recalc(user)
    deduct_tok(user, mult, f'Added {mult} stock trade(s)')
    wallet.refresh_from_db()
    return ok({'success': True, 'created_ids': ids, 'tokens_left': wallet.tokens}, status=201)


# ══════════════════════════════════════════════════════════════
#  TRADES — CREATE FOREX
# ══════════════════════════════════════════════════════════════

@login_required
@csrf_exempt
def api_forex_create(request):
    if request.method != 'POST': return err('Method not allowed.', 405)
    user = request.user
    try: d = json.loads(request.body)
    except: return err('Invalid body.')

    pair = d.get('pair', '').strip().upper()
    if not pair: return err('Forex pair is required.')

    direction = d.get('direction', '').strip().upper()
    if direction not in ('BUY', 'SELL'): return err('Direction must be BUY or SELL.')

    try:
        lot_size = float(d.get('lot_size', 0))
        if lot_size <= 0: raise ValueError()
    except: return err('Lot size must be > 0.')

    try:
        entry = float(d.get('entry_price', 0))
        exit_ = float(d.get('exit_price',  0))
        if entry <= 0 or exit_ <= 0: raise ValueError()
    except: return err('Prices must be positive.')

    # Pip calculation
    if 'JPY' in pair:
        pip_size = 0.01
    else:
        pip_size = 0.0001

    if direction == 'BUY':
        pips = round((exit_ - entry) / pip_size, 1)
    else:
        pips = round((entry - exit_) / pip_size, 1)

    # Standard lot = 100,000 units, pip value ≈ $10 per standard lot
    total_profit = round(pips * lot_size * 10, 2)

    broker   = d.get('broker',   '').strip()
    investor = d.get('investor', '').strip()
    notes    = d.get('notes',    '').strip()

    try: mult = max(1, min(100, int(d.get('multiplier', 1))))
    except: mult = 1

    wallet = user.wallet
    if wallet.tokens < mult:
        return ok({'token_error': True, 'tokens_available': wallet.tokens,
                   'tokens_needed': mult}, status=402)

    ids = []
    for _ in range(mult):
        t = Trade.objects.create(
            user=user, trade_type='FOREX', pair=pair, direction=direction,
            lot_size=round(lot_size, 2), entry_price=round(entry, 5),
            exit_price=round(exit_, 5), pips=pips, total_profit=total_profit,
            broker=broker, investor=investor, notes=notes)
        bump_stats(user, t)
        ids.append(t.id)

    recalc(user)
    deduct_tok(user, mult, f'Added {mult} forex trade(s)')
    wallet.refresh_from_db()
    return ok({'success': True, 'created_ids': ids, 'tokens_left': wallet.tokens}, status=201)


# ══════════════════════════════════════════════════════════════
#  TRADES — DETAIL  GET / PUT / DELETE
# ══════════════════════════════════════════════════════════════

@login_required
@csrf_exempt
def api_trade_detail(request, tid):
    user = request.user
    try: trade = user.trades.get(id=tid)
    except Trade.DoesNotExist: return err('Trade not found.', 404)

    if request.method == 'GET':
        d = trade_to_dict(trade)
        d['screenshot_b64'] = trade.screenshot_b64  # include full b64 on individual fetch
        return ok(d)

    if request.method == 'PUT':
        if trade.locked: return err('Trade is locked.')
        wallet = user.wallet
        if wallet.tokens < 1:
            return ok({'token_error': True, 'tokens_available': 0, 'tokens_needed': 1}, status=402)
        try: d = json.loads(request.body)
        except: return err('Invalid body.')

        if trade.trade_type == 'STOCK':
            sym = d.get('symbol', trade.symbol).strip().upper()
            if sym and not sym.isalpha(): return err('Symbol must be letters.')
            try:
                shr   = int(d.get('shares', trade.shares))
                entry = float(d.get('entry_price_share', trade.entry_price_share))
                exit_ = float(d.get('exit_price_share',  trade.exit_price_share))
                if shr <= 0 or entry <= 0 or exit_ <= 0: raise ValueError()
            except: return err('Invalid values.')
            if d.get('calc_mode') == 'custom':
                try: pps = float(d.get('profit_per_share', trade.profit_per_share))
                except: return err('Invalid profit per share.')
            else:
                pps = round(exit_ - entry, 4)
            trade.symbol            = sym
            trade.shares            = shr
            trade.entry_price_share = round(entry, 4)
            trade.exit_price_share  = round(exit_, 4)
            trade.profit_per_share  = round(pps, 4)
            trade.total_profit      = round(shr * pps, 2)
        else:  # FOREX
            try:
                entry = float(d.get('entry_price', trade.entry_price))
                exit_ = float(d.get('exit_price',  trade.exit_price))
                lot   = float(d.get('lot_size',    trade.lot_size))
                if entry <= 0 or exit_ <= 0 or lot <= 0: raise ValueError()
            except: return err('Invalid values.')
            direction = d.get('direction', trade.direction).upper()
            pip_size  = 0.01 if 'JPY' in trade.pair else 0.0001
            pips      = round(((exit_ - entry) if direction == 'BUY' else (entry - exit_)) / pip_size, 1)
            trade.entry_price  = round(entry, 5)
            trade.exit_price   = round(exit_, 5)
            trade.lot_size     = round(lot, 2)
            trade.direction    = direction
            trade.pips         = pips
            trade.total_profit = round(pips * lot * 10, 2)

        trade.broker   = d.get('broker',   trade.broker)
        trade.investor = d.get('investor', trade.investor)
        trade.notes    = d.get('notes',    trade.notes)
        trade.rating   = int(d.get('rating', trade.rating))
        trade.save()
        recalc(user)
        deduct_tok(user, 1, f'Edited Trade #{tid}')
        wallet.refresh_from_db()
        return ok({'success': True, 'tokens_left': wallet.tokens})

    if request.method == 'DELETE':
        wallet = user.wallet
        if wallet.tokens < 1:
            return ok({'token_error': True, 'tokens_available': 0, 'tokens_needed': 1}, status=402)
        trade.delete()
        recalc(user)
        deduct_tok(user, 1, f'Deleted Trade #{tid}')
        wallet.refresh_from_db()
        return ok({'success': True, 'tokens_left': wallet.tokens})

    return err('Method not allowed.', 405)


# ══════════════════════════════════════════════════════════════
#  SCREENSHOT — upload / get
# ══════════════════════════════════════════════════════════════

@login_required
@csrf_exempt
def api_screenshot(request, tid):
    user = request.user
    try: trade = user.trades.get(id=tid)
    except Trade.DoesNotExist: return err('Trade not found.', 404)

    if request.method == 'GET':
        return ok({'screenshot_b64': trade.screenshot_b64})

    if request.method == 'POST':
        try: d = json.loads(request.body)
        except: return err('Invalid body.')
        img = d.get('image_b64', '').strip()
        if not img: return err('No image data.')
        # Limit to ~2MB base64
        if len(img) > 2_800_000:
            return err('Image too large. Please use a screenshot under 2MB.')
        trade.screenshot_b64 = img
        trade.save(update_fields=['screenshot_b64'])
        return ok({'success': True})

    if request.method == 'DELETE':
        trade.screenshot_b64 = ''
        trade.save(update_fields=['screenshot_b64'])
        return ok({'success': True})

    return err('Method not allowed.', 405)


# ══════════════════════════════════════════════════════════════
#  BALANCE
# ══════════════════════════════════════════════════════════════

@login_required
def api_balance(request):
    if request.method != 'GET': return err('Method not allowed.', 405)
    user     = request.user
    profile  = get_profile(user)
    trades   = list(user.trades.order_by('id'))
    sb       = profile.starting_balance
    total_pl = round(sum(t.total_profit for t in trades), 2)
    cb       = round(sb + total_pl, 2)
    n        = len(trades)
    wins     = sum(1 for t in trades if t.total_profit > 0)
    losses   = sum(1 for t in trades if t.total_profit < 0)
    wr       = round(wins / n * 100, 1) if n > 0 else 0
    avg      = round(total_pl / n, 2)   if n > 0 else 0
    best     = max(trades, key=lambda t: t.total_profit, default=None)
    worst    = min(trades, key=lambda t: t.total_profit, default=None)
    wallet   = user.wallet

    def asset(t):
        return t.symbol if t.trade_type == 'STOCK' else t.pair

    return ok({
        'starting_balance': sb, 'current_balance': cb, 'total_pl': total_pl,
        'total_trades': n, 'wins': wins, 'losses': losses,
        'win_rate': wr, 'avg_pl': avg, 'tokens': wallet.tokens,
        'currency': profile.currency,
        'created_at': profile.created_at.strftime('%Y-%m-%d'),
        'best_trade':  {'symbol': asset(best),  'pl': best.total_profit}  if best  else None,
        'worst_trade': {'symbol': asset(worst), 'pl': worst.total_profit} if worst else None,
    })


# ══════════════════════════════════════════════════════════════
#  REVIEWS  (trade notes + rating)
# ══════════════════════════════════════════════════════════════

@login_required
def api_reviews(request):
    """GET all trades that have notes or a rating set."""
    if request.method != 'GET': return err('Method not allowed.', 405)
    trades = request.user.trades.exclude(notes='', rating=0).order_by('-id')
    data = []
    for t in trades:
        asset = t.symbol if t.trade_type == 'STOCK' else t.pair
        data.append({
            'id': t.id, 'trade_type': t.trade_type, 'asset': asset,
            'total_profit': t.total_profit, 'notes': t.notes,
            'rating': t.rating, 'has_screenshot': bool(t.screenshot_b64),
            'created_at': t.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return ok({'reviews': data})


@login_required
@csrf_exempt
def api_review_update(request, tid):
    """PATCH notes and rating on a trade (no token cost)."""
    if request.method != 'POST': return err('Method not allowed.', 405)
    user = request.user
    try: trade = user.trades.get(id=tid)
    except Trade.DoesNotExist: return err('Trade not found.', 404)
    try: d = json.loads(request.body)
    except: return err('Invalid body.')
    notes  = d.get('notes',  trade.notes)
    rating = int(d.get('rating', trade.rating))
    if not 0 <= rating <= 5: return err('Rating must be 0–5.')
    trade.notes  = notes
    trade.rating = rating
    trade.save(update_fields=['notes', 'rating'])
    return ok({'success': True})


# ══════════════════════════════════════════════════════════════
#  BROKERS
# ══════════════════════════════════════════════════════════════

@login_required
@csrf_exempt
def api_brokers(request):
    user = request.user
    if request.method == 'GET':
        return ok({'brokers': [{'id': b.id, 'name': b.name, 'spread': b.spread,
                                'wins': b.wins, 'losses': b.losses,
                                'win_rate': b.win_rate()} for b in user.brokers.all()]})
    if request.method == 'POST':
        try: d = json.loads(request.body)
        except: return err('Invalid body.')
        name = d.get('name', '').strip()
        if not name: return err('Name required.')
        try:
            spread = float(d.get('spread', 0))
            if spread <= 0: raise ValueError()
        except: return err('Spread must be > 0.')
        b = Broker.objects.create(user=user, name=name, spread=round(spread, 2))
        return ok({'success': True, 'id': b.id}, status=201)
    return err('Method not allowed.', 405)


@login_required
@csrf_exempt
def api_broker_detail(request, bid):
    try: b = request.user.brokers.get(id=bid)
    except Broker.DoesNotExist: return err('Not found.', 404)
    if request.method == 'DELETE':
        if request.user.trades.filter(broker=b.name).exists():
            return err('Cannot delete — broker used in trades.')
        b.delete()
        return ok({'success': True})
    return err('Method not allowed.', 405)


# ══════════════════════════════════════════════════════════════
#  INVESTORS
# ══════════════════════════════════════════════════════════════

@login_required
@csrf_exempt
def api_investors(request):
    user = request.user
    if request.method == 'GET':
        return ok({'investors': [{'id': i.id, 'name': i.name, 'wins': i.wins,
                                  'losses': i.losses, 'net_pl': i.net_pl,
                                  'win_rate': i.win_rate()} for i in user.investors.all()]})
    if request.method == 'POST':
        try: d = json.loads(request.body)
        except: return err('Invalid body.')
        name = d.get('name', '').strip()
        if not name: return err('Name required.')
        i = Investor.objects.create(user=user, name=name)
        return ok({'success': True, 'id': i.id}, status=201)
    return err('Method not allowed.', 405)


@login_required
@csrf_exempt
def api_investor_detail(request, iid):
    try: i = request.user.investors.get(id=iid)
    except Investor.DoesNotExist: return err('Not found.', 404)
    if request.method == 'DELETE':
        if request.user.trades.filter(investor=i.name).exists():
            return err('Cannot delete — investor used in trades.')
        i.delete()
        return ok({'success': True})
    return err('Method not allowed.', 405)


# ══════════════════════════════════════════════════════════════
#  TOKENS
# ══════════════════════════════════════════════════════════════

@login_required
@csrf_exempt
def api_tokens(request):
    user   = request.user
    wallet = user.wallet
    if request.method == 'GET':
        hist = [{'action': h.action, 'change': h.change, 'balance': h.balance,
                 'time': h.created_at.strftime('%Y-%m-%d %H:%M')}
                for h in user.token_history.order_by('-created_at')[:30]]
        return ok({'tokens': wallet.tokens, 'total_earned': wallet.total_earned,
                   'total_used': wallet.total_used, 'history': hist})
    if request.method == 'POST':
        try: d = json.loads(request.body)
        except: return err('Invalid body.')
        code = d.get('code', '').strip()
        if code == GIFT_CODE:
            return ok({'success': True, 'tokens': add_tok(user, 10, 'Gift Code')})
        if code == '__AD_REWARD__':
            return ok({'success': True, 'tokens': add_tok(user, 10, 'Watched Ad')})
        return err('Invalid gift code.', 400)
    return err('Method not allowed.', 405)


# ══════════════════════════════════════════════════════════════
#  AI ANALYSIS
# ══════════════════════════════════════════════════════════════

@login_required
def api_ai(request):
    if request.method != 'GET': return err('Method not allowed.', 405)
    user      = request.user
    trades    = list(user.trades.all())
    brokers   = list(user.brokers.all())
    investors = list(user.investors.all())
    best_b    = min(brokers, key=lambda b: b.spread, default=None)

    broker_stats = [{'name': b.name, 'spread': b.spread, 'wins': b.wins,
                     'losses': b.losses, 'win_rate': b.win_rate()} for b in brokers]
    inv_stats    = [{'name': i.name, 'wins': i.wins, 'losses': i.losses,
                     'net_pl': i.net_pl, 'win_rate': i.win_rate()} for i in investors]

    syms = {}
    for t in trades:
        key = t.symbol if t.trade_type == 'STOCK' else t.pair
        if key not in syms: syms[key] = {'n': 0, 'w': 0, 'pl': 0, 'min': None, 'type': t.trade_type}
        syms[key]['n'] += 1
        if t.total_profit > 0: syms[key]['w'] += 1
        syms[key]['pl'] = round(syms[key]['pl'] + t.total_profit, 2)
        ep = t.entry_price_share if t.trade_type == 'STOCK' else t.entry_price
        if syms[key]['min'] is None or ep < syms[key]['min']:
            syms[key]['min'] = ep

    sym_stats = [{'symbol': s, 'type': d['type'], 'trades': d['n'], 'wins': d['w'],
                  'win_rate': round(d['w'] / d['n'] * 100, 1) if d['n'] else 0,
                  'avg_pl': round(d['pl'] / d['n'], 2) if d['n'] else 0,
                  'min_entry': d['min']} for s, d in syms.items()]
    sym_stats.sort(key=lambda x: x['win_rate'], reverse=True)

    return ok({'best_broker': {'name': best_b.name, 'spread': best_b.spread} if best_b else None,
               'broker_stats': broker_stats, 'investor_stats': inv_stats,
               'symbol_stats': sym_stats})


# ══════════════════════════════════════════════════════════════
#  CHAT
# ══════════════════════════════════════════════════════════════

@login_required
def api_chat(request):
    if request.method != 'GET':
        return err('Method not allowed.', 405)

    since_id = request.GET.get('since', '0')
    try:    since_id = int(since_id)
    except: since_id = 0

    # select_related('user') avoids N+1 queries on username
    qs = ChatMessage.objects.select_related('user')

    if since_id > 0:
        # Poll: only return messages newer than last seen
        msgs = list(qs.filter(id__gt=since_id).order_by('created_at')[:CHAT_FETCH_LIMIT])
    else:
        # First load: return last 80 messages in chronological order
        msgs = list(qs.order_by('-created_at')[:CHAT_FETCH_LIMIT])
        msgs = list(reversed(msgs))

    current_user_id = request.user.id
    data = [{
        'id':       m.id,
        'username': m.user.username,
        'message':  m.message,
        'time':     m.created_at.strftime('%H:%M'),
        'is_me':    m.user_id == current_user_id,   # True only for the requesting user
    } for m in msgs]

    return ok({'messages': data, 'count': len(data)})


@login_required
@csrf_exempt
def api_chat_send(request):
    if request.method != 'POST': return err('Method not allowed.', 405)
    user = request.user

    # Rate limit: max 1 message per 3 seconds per user
    recent = ChatMessage.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timedelta(seconds=CHAT_RATE_LIMIT)
    ).exists()
    if recent:
        return err('You are sending messages too fast. Please wait a moment.', 429)

    try: d = json.loads(request.body)
    except: return err('Invalid body.')

    message = d.get('message', '').strip()
    if not message:
        return err('Message cannot be empty.')
    if len(message) > CHAT_MAX_LEN:
        return err(f'Message too long. Max {CHAT_MAX_LEN} characters.')

    # Basic profanity/spam: block repeated characters
    if len(set(message.lower())) < 2 and len(message) > 5:
        return err('Invalid message.')

    msg = ChatMessage.objects.create(user=user, message=message)
    return ok({'success': True, 'id': msg.id,
               'username': user.username,
               'message': msg.message,
               'time': msg.created_at.strftime('%H:%M')}, status=201)


# ══════════════════════════════════════════════════════════════
#  RESET
# ══════════════════════════════════════════════════════════════

@login_required
@csrf_exempt
def api_reset(request):
    if request.method != 'POST': return err('Method not allowed.', 405)
    try: d = json.loads(request.body)
    except: return err('Invalid body.')
    step = d.get('step')

    if step == 'init':
        c1 = random.choice(string.ascii_letters)
        c2 = str(random.randint(0, 9))
        c3 = random.choice(string.ascii_uppercase + string.digits)
        request.session['reset_codes'] = [c1, c2, c3]
        request.session.modified = True
        return ok({'c1': c1, 'c2': c2, 'c3': c3})

    if step == 'verify':
        saved  = request.session.get('reset_codes', [])
        inputs = d.get('inputs', [])
        if not saved or inputs != saved:
            return err('Confirmation failed.')
        user = request.user
        user.trades.all().delete()
        user.brokers.all().delete()
        user.investors.all().delete()
        user.token_history.all().delete()
        TokenWallet.objects.filter(user=user).delete()
        p = user.profile
        p.starting_balance = 0.0
        p.initialized      = False
        p.save()
        for name, spread in DEFAULT_BROKERS:
            Broker.objects.create(user=user, name=name, spread=spread)
        for name in DEFAULT_INVESTORS:
            Investor.objects.create(user=user, name=name)
        TokenWallet.objects.create(user=user)
        del request.session['reset_codes']
        return ok({'success': True})

    return err('Unknown step.', 400)
