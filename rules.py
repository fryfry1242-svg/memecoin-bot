import time

# ---- Your paper strategies. Change these numbers to be stricter or looser. ----
# scanner.py, rug_filter.py, ticket_bot.py, auto_tickets.py and export_results.py all read them
# from this one file. A rule set to None is switched off for that strategy.
# The scanner only lists tokens that pass baseline, so other strategies should be stricter than it.
STRATEGIES = {
    "baseline": {
        "min_liquidity_usd": 25000,        # money sitting in the pool
        "min_volume_24h_usd": 10000,       # money traded in the last 24 hours
        "min_age_hours": 24,               # how old the trading pair must be
        "min_trades_24h": 100,             # total buys + sells in the last 24 hours
        "min_liquidity_to_mcap": 0.02,     # liquidity must be at least 2% of market cap
        "min_mcap_usd": None,              # market cap range (off for baseline)
        "max_mcap_usd": None,
        "min_volume_to_liquidity": None,   # 24h volume as a share of liquidity (off for baseline)
    },
    "medium_risk": {
        "min_liquidity_usd": 50000,
        "min_volume_24h_usd": 10000,
        "min_age_hours": 72,
        "min_trades_24h": 200,
        "min_liquidity_to_mcap": 0.05,
        "min_mcap_usd": 1_000_000,
        "max_mcap_usd": 25_000_000,
        "min_volume_to_liquidity": 0.5,
    },
}
DEFAULT_STRATEGY = "baseline"

# The honeypot check is the same for every strategy.
HONEYPOT_MIN_BUYS = 20          # the honeypot check starts at this many buys...
HONEYPOT_MAX_SELL_RATIO = 0.05  # ...and fails if sells are 5% of buys or fewer


def get_strategy(name):
    if not isinstance(name, str) or name not in STRATEGIES:
        raise ValueError(f"unknown strategy {name!r} (use one of: {', '.join(STRATEGIES)})")
    return STRATEGIES[name]


def check_token(pair, strategy=DEFAULT_STRATEGY):
    """Return a list of (short reason, detailed message) problems. Empty list means it passed."""
    rules = get_strategy(strategy)
    problems = []

    liquidity = (pair.get("liquidity") or {}).get("usd") or 0
    volume = (pair.get("volume") or {}).get("h24") or 0
    txns = (pair.get("txns") or {}).get("h24") or {}
    buys = txns.get("buys") or 0
    sells = txns.get("sells") or 0
    mcap = pair.get("marketCap") or pair.get("fdv") or 0
    created_ms = pair.get("pairCreatedAt")

    if liquidity < rules["min_liquidity_usd"]:
        problems.append(("low liquidity",
                         f"Liquidity too low: ${liquidity:,.0f} (need ${rules['min_liquidity_usd']:,})"))

    if volume < rules["min_volume_24h_usd"]:
        problems.append(("low volume",
                         f"24h volume too low: ${volume:,.0f} (need ${rules['min_volume_24h_usd']:,})"))

    if created_ms:
        age_hours = (time.time() * 1000 - created_ms) / 3600000
        if age_hours < rules["min_age_hours"]:
            problems.append(("too new",
                             f"Too new: {age_hours:.1f} hours old (need {rules['min_age_hours']}+)"))
    else:
        problems.append(("unknown age", "Could not find the pair's age"))

    if buys + sells < rules["min_trades_24h"]:
        problems.append(("few trades",
                         f"Too few trades: {buys + sells} in 24h (need {rules['min_trades_24h']})"))

    # Lots of buys but almost no sells can mean people are not able to sell (a honeypot).
    if buys >= HONEYPOT_MIN_BUYS and sells <= buys * HONEYPOT_MAX_SELL_RATIO:
        problems.append(("buys but no sells", f"Suspicious: {buys} buys but only {sells} sells"))

    if mcap and liquidity / mcap < rules["min_liquidity_to_mcap"]:
        pct = liquidity / mcap * 100
        problems.append(("thin liquidity vs market cap",
                         f"Liquidity is only {pct:.1f}% of market cap (easy to drain)"))

    low, high = rules["min_mcap_usd"], rules["max_mcap_usd"]
    if low is not None or high is not None:
        if not mcap:
            problems.append(("unknown market cap", "Could not find the market cap"))
        elif low is not None and mcap < low:
            problems.append(("market cap too small", f"Market cap too small: ${mcap:,.0f} (need ${low:,}+)"))
        elif high is not None and mcap > high:
            problems.append(("market cap too big", f"Market cap too big: ${mcap:,.0f} (max ${high:,})"))

    ratio = rules["min_volume_to_liquidity"]
    if ratio is not None and volume < liquidity * ratio:
        problems.append(("low volume vs liquidity",
                         f"24h volume is only {volume / liquidity:.0%} of liquidity (need {ratio:.0%}+)"))

    return problems


def describe_rules(strategy=DEFAULT_STRATEGY):
    """A strategy's rules in plain language. The scanner saves these for the dashboard's Rules tab."""
    rules = get_strategy(strategy)
    lines = [
        f"Liquidity of at least ${rules['min_liquidity_usd']:,} (money sitting in the trading pool)",
        f"At least ${rules['min_volume_24h_usd']:,} traded in the last 24 hours",
        f"Trading pair at least {rules['min_age_hours']} hours old",
        f"At least {rules['min_trades_24h']} trades in the last 24 hours",
        f"Not many buys with almost no sells: with {HONEYPOT_MIN_BUYS}+ buys, sells must be more than "
        f"{HONEYPOT_MAX_SELL_RATIO:.0%} of buys (a honeypot sign)",
        f"Liquidity at least {rules['min_liquidity_to_mcap']:.0%} of market cap (harder to drain)",
    ]
    low, high = rules["min_mcap_usd"], rules["max_mcap_usd"]
    if low is not None and high is not None:
        lines.append(f"Market cap between ${low:,} and ${high:,}")
    elif low is not None:
        lines.append(f"Market cap of at least ${low:,}")
    elif high is not None:
        lines.append(f"Market cap of at most ${high:,}")
    if rules["min_volume_to_liquidity"] is not None:
        lines.append(f"24h volume at least {rules['min_volume_to_liquidity']:.0%} of liquidity "
                     "(shows real trading)")
    return lines
