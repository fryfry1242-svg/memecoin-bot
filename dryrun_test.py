import json

import requests

from jupiter_dryrun import DEFAULT_USD, get_decimals, round_trip

# Quotes a few tokens from data.json with Jupiter (DRY RUN, nothing is bought or sold): the buy
# price against DexScreener's live price, then selling the same tokens straight back to USDC.
HOW_MANY = 3   # the most liquid tokens, plus the least liquid one for contrast


def live_dexscreener_prices(addresses):
    """Price of each token's most liquid pair right now. data.json can be 15 minutes old."""
    url = "https://api.dexscreener.com/tokens/v1/solana/" + ",".join(addresses)
    best = {}
    for p in requests.get(url, timeout=15).json() or []:
        address = (p.get("baseToken") or {}).get("address")
        liquidity = (p.get("liquidity") or {}).get("usd") or 0
        if address and p.get("priceUsd") and liquidity > best.get(address, (0, 0))[1]:
            best[address] = (float(p["priceUsd"]), liquidity)
    return {a: price for a, (price, liquidity) in best.items()}


def main():
    with open("data.json") as f:
        candidates = json.load(f)["candidates"]
    picks = candidates[:HOW_MANY]
    if len(candidates) > HOW_MANY:
        picks.append(candidates[-1])
    if not picks:
        print("No tokens in data.json. Run the scanner first.")
        return

    addresses = [c["address"] for c in picks]
    print(f"DRY RUN: quoting ${DEFAULT_USD} of USDC into {len(picks)} tokens and back. Nothing is bought or sold.\n")
    decimals = get_decimals(addresses)
    try:
        dex_prices = live_dexscreener_prices(addresses)
    except requests.RequestException:
        print("Could not get live DexScreener prices, using the (older) data.json prices.\n")
        dex_prices = {}

    for c in picks:
        address = c["address"]
        name = f"{c['symbol']} (liquidity ${c['liquidity_usd']:,.0f})"
        try:
            trip = round_trip(address, decimals=decimals.get(address))
        except (requests.RequestException, RuntimeError) as error:
            print(f"{name}: no quote - {error}\n")
            continue
        quote, sell = trip["buy"], trip["sell"]
        dex_price = dex_prices.get(address) or float(c["price_usd"])
        print(name)
        print(f"  BUY ${DEFAULT_USD} USDC")
        print(f"  Route:            {' -> '.join(quote['route']) or '?'} (via {quote['router']})")
        impact = quote["price_impact_pct"]
        print(f"  Price impact:     {'?' if impact is None else f'{impact:.2f}%'} (as reported by Jupiter)")
        if quote["out_tokens"] is None:
            print(f"  Would get:        {quote['out_amount_raw']} raw units (decimals unknown, can't compare)")
        else:
            worth = quote["out_tokens"] * dex_price
            diff = (quote["effective_price_usd"] / dex_price - 1) * 100
            print(f"  Would get:        {quote['out_tokens']:,.2f} tokens")
            print(f"  Jupiter price:    ${quote['effective_price_usd']:.10f} per token")
            print(f"  DexScreener:      ${dex_price:.10f} per token")
            print(f"  Difference:       {diff:+.2f}% (positive = you pay more than DexScreener shows)")
            print(f"  Hidden cost:      ${DEFAULT_USD - worth:+.4f} of your ${DEFAULT_USD} "
                  f"(tokens worth ${worth:.4f} at DexScreener's price)")
        print("  SELL the same tokens straight back")
        print(f"  Route:            {' -> '.join(sell['route']) or '?'} (via {sell['router']})")
        sell_impact = sell["price_impact_pct"]
        print(f"  Price impact:     {'?' if sell_impact is None else f'{sell_impact:.2f}%'} (as reported by Jupiter)")
        print(f"  Would get back:   ${sell['usd_out']:.4f} USDC")
        print(f"  ROUND-TRIP COST:  ${trip['cost_usd']:.4f} ({trip['cost_pct']:.2f}% of ${DEFAULT_USD})\n")
    print("Round-trip cost = what you'd lose buying and selling at once, before the price moves at all.")


main()
