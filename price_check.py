import sys
import requests

# Which blockchain to look at. Change "solana" to "base" or "ethereum" if you trade there.
CHAIN = "solana"


def search_pairs(query):
    """Ask DexScreener for trading pairs that match a name or token address."""
    url = "https://api.dexscreener.com/latest/dex/search"
    response = requests.get(url, params={"q": query}, timeout=10)
    response.raise_for_status()
    return response.json().get("pairs") or []


def liquidity_usd(pair):
    return (pair.get("liquidity") or {}).get("usd") or 0


def main():
    # Use the word you type after the script name, or default to BONK
    query = sys.argv[1] if len(sys.argv) > 1 else "BONK"

    pairs = [p for p in search_pairs(query) if p.get("chainId") == CHAIN]
    pairs.sort(key=liquidity_usd, reverse=True)

    if not pairs:
        print(f"No {CHAIN} pairs found for '{query}'")
        return

    print(f"Top results for '{query}' on {CHAIN}:\n")
    for p in pairs[:5]:
        token = p.get("baseToken") or {}
        volume = (p.get("volume") or {}).get("h24") or 0
        change = (p.get("priceChange") or {}).get("h24")
        print(f"{token.get('name')} ({token.get('symbol')})")
        print(f"  Price:      ${p.get('priceUsd')}")
        print(f"  Liquidity:  ${liquidity_usd(p):,.0f}")
        print(f"  24h volume: ${volume:,.0f}")
        print(f"  24h change: {change}%")
        print(f"  Address:    {token.get('address')}")
        print()


main()
