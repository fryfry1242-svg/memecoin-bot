import sys
import requests

from rules import check_token  # the safety rules live in rules.py

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

    problems = [detail for reason, detail in check_token(pair)]
    if problems:
        print("RESULT: FAIL - do not buy")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("RESULT: PASS - cleared every check")
        print("(Passing does not mean safe. It only means no red flags were found.)")


main()
