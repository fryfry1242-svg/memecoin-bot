import time

# ---- Your safety rules. Change these numbers to be stricter or looser. ----
# scanner.py, rug_filter.py and ticket_bot.py all read them from this one file.
MIN_LIQUIDITY_USD = 25000       # money sitting in the pool
MIN_VOLUME_24H_USD = 10000      # money traded in the last 24 hours
MIN_AGE_HOURS = 24              # how old the trading pair must be
MIN_TRADES_24H = 100            # total buys + sells in the last 24 hours
MIN_LIQUIDITY_TO_MCAP = 0.02    # liquidity must be at least 2% of market cap
HONEYPOT_MIN_BUYS = 20          # the honeypot check starts at this many buys...
HONEYPOT_MAX_SELL_RATIO = 0.05  # ...and fails if sells are 5% of buys or fewer


def check_token(pair):
    """Return a list of (short reason, detailed message) problems. Empty list means it passed."""
    problems = []

    liquidity = (pair.get("liquidity") or {}).get("usd") or 0
    volume = (pair.get("volume") or {}).get("h24") or 0
    txns = (pair.get("txns") or {}).get("h24") or {}
    buys = txns.get("buys") or 0
    sells = txns.get("sells") or 0
    mcap = pair.get("marketCap") or pair.get("fdv") or 0
    created_ms = pair.get("pairCreatedAt")

    if liquidity < MIN_LIQUIDITY_USD:
        problems.append(("low liquidity",
                         f"Liquidity too low: ${liquidity:,.0f} (need ${MIN_LIQUIDITY_USD:,})"))

    if volume < MIN_VOLUME_24H_USD:
        problems.append(("low volume",
                         f"24h volume too low: ${volume:,.0f} (need ${MIN_VOLUME_24H_USD:,})"))

    if created_ms:
        age_hours = (time.time() * 1000 - created_ms) / 3600000
        if age_hours < MIN_AGE_HOURS:
            problems.append(("too new",
                             f"Too new: {age_hours:.1f} hours old (need {MIN_AGE_HOURS}+)"))
    else:
        problems.append(("unknown age", "Could not find the pair's age"))

    if buys + sells < MIN_TRADES_24H:
        problems.append(("few trades",
                         f"Too few trades: {buys + sells} in 24h (need {MIN_TRADES_24H})"))

    # Lots of buys but almost no sells can mean people are not able to sell (a honeypot).
    if buys >= HONEYPOT_MIN_BUYS and sells <= buys * HONEYPOT_MAX_SELL_RATIO:
        problems.append(("buys but no sells", f"Suspicious: {buys} buys but only {sells} sells"))

    if mcap and liquidity / mcap < MIN_LIQUIDITY_TO_MCAP:
        pct = liquidity / mcap * 100
        problems.append(("thin liquidity vs market cap",
                         f"Liquidity is only {pct:.1f}% of market cap (easy to drain)"))

    return problems


def describe_rules():
    """The rules in plain language. The scanner saves this list for the dashboard's Rules tab."""
    return [
        f"Liquidity of at least ${MIN_LIQUIDITY_USD:,} (money sitting in the trading pool)",
        f"At least ${MIN_VOLUME_24H_USD:,} traded in the last 24 hours",
        f"Trading pair at least {MIN_AGE_HOURS} hours old",
        f"At least {MIN_TRADES_24H} trades in the last 24 hours",
        f"Not many buys with almost no sells: with {HONEYPOT_MIN_BUYS}+ buys, sells must be more than "
        f"{HONEYPOT_MAX_SELL_RATIO:.0%} of buys (a honeypot sign)",
        f"Liquidity at least {MIN_LIQUIDITY_TO_MCAP:.0%} of market cap (harder to drain)",
    ]
