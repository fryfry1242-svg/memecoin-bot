import sys
import time
import requests

# ---- Your safety rules. Change these numbers to be stricter or looser. ----
MIN_LIQUIDITY_USD = 25000    # money sitting in the pool
MIN_VOLUME_24H_USD = 10000   # money traded in the last 24 hours
MIN_AGE_HOURS = 24           # how old the trading pair must be
MIN_TRADES_24H = 100         # total buys + sells in the last 24 hours
MIN_LIQUIDITY_TO_MCAP = 0.02 # liquidity must be at least 2% of market cap
CHAIN = "solana"


def get_best_pair(address):
    """Look up a token by its address and return its most liquid pair."""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    pairs = response.json().get("pairs") or []
    pairs = [p for p in pairs if p.get("chainId") == CHAIN]
    if not pairs:
        return None
    pairs.sort(key=lambda p: (p.get("liquidity") or {}).get("usd") or 0, reverse=True)
    return pairs[0]


def check_token(pair):
    """Return a list of problems. An empty list means it passed every check."""
    problems = []

    liquidity = (pair.get("liquidity") or {}).get("usd") or 0
    volume = (pair.get("volume") or {}).get("h24") or 0
    txns = (pair.get("txns") or {}).get("h24") or {}
    buys = txns.get("buys") or 0
    sells = txns.get("sells") or 0
    mcap = pair.get("marketCap") or pair.get("fdv") or 0
    created_ms = pair.get("pairCreatedAt")

    if liquidity < MIN_LIQUIDITY_USD:
        problems.append(f"Liquidity too low: ${liquidity:,.0f} (need ${MIN_LIQUIDITY_USD:,})")

    if volume < MIN_VOLUME_24H_USD:
        problems.append(f"24h volume too low: ${volume:,.0f} (need ${MIN_VOLUME_24H_USD:,})")

    if created_ms:
        age_hours = (time.time() * 1000 - created_ms) / 3600000
        if age_hours < MIN_AGE_HOURS:
            problems.append(f"Too new: {age_hours:.1f} hours old (need {MIN_AGE_HOURS}+)")
    else:
        problems.append("Could not find the pair's age")

    if buys + sells < MIN_TRADES_24H:
        problems.append(f"Too few trades: {buys + sells} in 24h (need {MIN_TRADES_24H})")

    # Lots of buys but almost no sells can mean people are not able to sell (a honeypot).
    if buys >= 20 and sells <= buys * 0.05:
        problems.append(f"Suspicious: {buys} buys but only {sells} sells")

    if mcap and liquidity / mcap < MIN_LIQUIDITY_TO_MCAP:
        pct = liquidity / mcap * 100
        problems.append(f"Liquidity is only {pct:.1f}% of market cap (easy to drain)")

    return problems


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 rug_filter.py TOKEN_ADDRESS")
        return

    address = sys.argv[1]
    pair = get_best_pair(address)
    if pair is None:
        print(f"No {CHAIN} trading pair found for that address.")
        return

    token = pair.get("baseToken") or {}
    print(f"Checking {token.get('name')} ({token.get('symbol')})")
    print(f"Price: ${pair.get('priceUsd')}\n")

    problems = check_token(pair)
    if problems:
        print("RESULT: FAIL - do not buy")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("RESULT: PASS - cleared every check")
        print("(Passing does not mean safe. It only means no red flags were found.)")


main()
