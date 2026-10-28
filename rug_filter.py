import sys
import requests

from rules import DEFAULT_STRATEGY, STRATEGIES, check_token  # the safety rules live in rules.py

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


def main():
    if len(sys.argv) < 2:
        print(f"Usage: venv/bin/python rug_filter.py TOKEN_ADDRESS [{' | '.join(STRATEGIES)}]")
        return

    address = sys.argv[1]
    strategy = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_STRATEGY
    if strategy not in STRATEGIES:
        print(f"Unknown strategy {strategy!r}. Use one of: {', '.join(STRATEGIES)}")
        return
    pair = get_best_pair(address)
    if pair is None:
        print(f"No {CHAIN} trading pair found for that address.")
        return

    token = pair.get("baseToken") or {}
    print(f"Checking {token.get('name')} ({token.get('symbol')}) with the {strategy} rules")
    print(f"Price: ${pair.get('priceUsd')}\n")

    problems = [detail for reason, detail in check_token(pair, strategy)]
    if problems:
        print("RESULT: FAIL - do not buy")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("RESULT: PASS - cleared every check")
        print("(Passing does not mean safe. It only means no red flags were found.)")


main()
