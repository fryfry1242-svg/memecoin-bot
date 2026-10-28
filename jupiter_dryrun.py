import sys
import time

import requests

# DRY RUN ONLY. This file asks Jupiter "what would I get if I swapped?" and nothing more.
# It never uses a wallet, keys, signing, or transactions. Leaving out the "taker" (wallet)
# parameter is what tells Jupiter to return a quote only, with no transaction.
# Docs: https://developers.jup.ag/docs/swap/order-and-execute

BASE_URL = "https://api.jup.ag"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDC_DECIMALS = 6            # 1 USDC = 1,000,000 of its smallest unit
DEFAULT_USD = 5              # assumes 1 USDC = $1
REQUEST_GAP_SECONDS = 2.1    # Jupiter allows 0.5 requests per second without an API key

_last_request = 0.0


def _get(path, params):
    """GET from Jupiter, waiting first so we stay under the free speed limit."""
    global _last_request
    wait = REQUEST_GAP_SECONDS - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.time()
    response = requests.get(BASE_URL + path, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def get_decimals(addresses):
    """Map each token address to its number of decimal places (one request for up to 100)."""
    tokens = _get("/tokens/v2/search", {"query": ",".join(addresses)})
    return {t["id"]: t["decimals"] for t in tokens if "id" in t and "decimals" in t}


def describe_route(route_plan):
    """One entry per hop, e.g. ["Meteora DLMM 15% + Kipseli 85%", "Pump.fun Amm"].
    Steps with the same input and output token are a split of one hop, not separate hops."""
    hops = []
    for step in route_plan:
        info = step.get("swapInfo") or {}
        key = (info.get("inputMint"), info.get("outputMint"))
        if hops and hops[-1][0] == key:
            hops[-1][1].append(step)
        else:
            hops.append((key, [step]))
    names = []
    for key, steps in hops:
        if len(steps) == 1:
            names.append((steps[0].get("swapInfo") or {}).get("label", "?"))
        else:
            names.append(" + ".join(f"{(s.get('swapInfo') or {}).get('label', '?')} {s.get('percent', 0):.0f}%"
                                    for s in steps))
    return names


def get_quote(token_address, usd_amount=DEFAULT_USD, decimals=None):
    """Quote swapping usd_amount of USDC into token_address. Returns a dict, never a transaction."""
    data = _get("/swap/v2/order", {
        "inputMint": USDC_MINT,
        "outputMint": token_address,
        "amount": str(int(usd_amount * 10 ** USDC_DECIMALS)),
    })
    if data.get("transaction"):
        raise RuntimeError("Jupiter returned a transaction. This dry-run module refuses to use it.")
    if data.get("error") or data.get("errorMessage") or "outAmount" not in data:
        raise RuntimeError(f"No quote: {data.get('error') or data.get('errorMessage') or 'missing outAmount'}")

    out_raw = int(data["outAmount"])
    out_tokens = out_raw / 10 ** decimals if decimals is not None else None
    return {
        "usd_in": usd_amount,
        "out_amount_raw": out_raw,
        "out_tokens": out_tokens,
        "price_impact_pct": data.get("priceImpact"),   # percentage points, e.g. -0.1 means -0.1%
        "route": describe_route(data.get("routePlan") or []),
        "router": data.get("router"),
        "effective_price_usd": usd_amount / out_tokens if out_tokens else None,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: venv/bin/python jupiter_dryrun.py TOKEN_ADDRESS")
        sys.exit(1)
    address = sys.argv[1]
    quote = get_quote(address, decimals=get_decimals([address]).get(address))
    print(f"DRY RUN quote for ${quote['usd_in']} of USDC -> {address}")
    print(f"  You would get: {quote['out_tokens']} tokens ({quote['out_amount_raw']} raw)")
    print(f"  Price per token: ${quote['effective_price_usd']}")
    print(f"  Price impact: {quote['price_impact_pct']}%")
    print(f"  Route: {' -> '.join(quote['route'])} (via {quote['router']})")
