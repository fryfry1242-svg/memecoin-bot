import json
import sys
import time
from datetime import datetime, timezone

import requests

from rules import STRATEGIES, check_token, describe_rules

CHAIN = "solana"

SOURCES = [
    "https://api.dexscreener.com/token-profiles/latest/v1",
    "https://api.dexscreener.com/token-boosts/latest/v1",
    "https://api.dexscreener.com/token-boosts/top/v1",
]


def fetch_json(url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def collect_addresses():
    addresses = []
    for url in SOURCES:
        try:
            for item in fetch_json(url):
                address = item.get("tokenAddress")
                if item.get("chainId") == CHAIN and address and address not in addresses:
                    addresses.append(address)
        except Exception as error:
            print(f"Source failed ({url}): {error}")
    return addresses


def get_pairs(addresses):
    pairs = []
    for i in range(0, len(addresses), 30):
        chunk = addresses[i:i + 30]
        url = f"https://api.dexscreener.com/tokens/v1/{CHAIN}/{','.join(chunk)}"
        try:
            data = fetch_json(url)
            if isinstance(data, list):
                pairs.extend(data)
        except Exception as error:
            print(f"Lookup failed: {error}")
        time.sleep(1)
    return pairs


def best_pair_per_token(pairs):
    best = {}
    for p in pairs:
        address = (p.get("baseToken") or {}).get("address")
        if not address:
            continue
        liquidity = (p.get("liquidity") or {}).get("usd") or 0
        current = best.get(address)
        if current is None or liquidity > ((current.get("liquidity") or {}).get("usd") or 0):
            best[address] = p
    return list(best.values())


def main():
    addresses = collect_addresses()
    if not addresses:
        print("No addresses collected. Not updating data.json.")
        sys.exit(1)

    pairs = best_pair_per_token(get_pairs(addresses))
    candidates = []
    reasons = {}

    for p in pairs:
        problems = [reason for reason, detail in check_token(p)]
        for reason in problems:
            reasons[reason] = reasons.get(reason, 0) + 1
        if problems:
            continue
        token = p.get("baseToken") or {}
        txns = (p.get("txns") or {}).get("h24") or {}
        candidates.append({
            "name": token.get("name"),
            "symbol": token.get("symbol"),
            "address": token.get("address"),
            "price_usd": p.get("priceUsd"),
            "liquidity_usd": (p.get("liquidity") or {}).get("usd"),
            "volume_24h": (p.get("volume") or {}).get("h24"),
            "change_24h": (p.get("priceChange") or {}).get("h24"),
            "trades_24h": (txns.get("buys") or 0) + (txns.get("sells") or 0),
            "age_hours": round((time.time() * 1000 - p["pairCreatedAt"]) / 3600000),
            "url": p.get("url"),
            "market_cap": p.get("marketCap") or p.get("fdv"),
            # Which paper strategies this token passes. auto_tickets.py uses this.
            "strategies": [name for name in STRATEGIES if not check_token(p, name)],
        })

    candidates.sort(key=lambda c: c.get("liquidity_usd") or 0, reverse=True)

    result = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "scanned": len(pairs),
        "passed": len(candidates),
        "rejection_reasons": reasons,
        "rules": describe_rules(),
        "strategy_rules": {name: describe_rules(name) for name in STRATEGIES},
        "candidates": candidates[:25],
    }
    with open("data.json", "w") as f:
        json.dump(result, f, indent=2)
    print(f"Scanned {len(pairs)} tokens, {len(candidates)} passed.")


main()
