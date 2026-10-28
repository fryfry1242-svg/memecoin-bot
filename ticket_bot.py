import glob
import json
import os
import shutil
import time
from datetime import datetime, timezone

import requests

from rules import DEFAULT_STRATEGY, get_strategy, check_token  # each ticket must pass its strategy's rules

# ---- Settings ----
CHAIN = "solana"
SLIPPAGE_PCT = 2        # pretend we lose 2% on every buy and sell
CHECK_SECONDS = 10      # how often to check tickets and prices
LOG_FILE = "paper_trades.log"
POSITIONS_FILE = "positions.json"   # open paper trades are saved here between runs

# ---- Default rules, used when a ticket doesn't set its own ----
DEFAULTS = {
    "strategy": DEFAULT_STRATEGY,   # which rule set in rules.py the token must pass
    "size_usd": 20,
    "take_profit_mult": 2.0,
    "sell_fraction_at_tp": 0.5,
    "trailing_stop_pct": 30,
    "hard_stop_pct": 40,
}

for folder in ("orders", "orders/open", "orders/done", "orders/rejected"):
    os.makedirs(folder, exist_ok=True)


def log(message):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def label(pos):
    """Name used in log lines, e.g. "GLITCH (medium_risk)". The same token can be open in two strategies."""
    return f"{pos['symbol']} ({pos['ticket'].get('strategy', DEFAULT_STRATEGY)})"


def save_positions(positions):
    """Write open positions to a temp file, then swap it in, so a crash never leaves half a file."""
    tmp = POSITIONS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(positions, f, indent=2)
    os.replace(tmp, POSITIONS_FILE)


def load_positions():
    """Read positions saved by an earlier run. Skip any whose ticket file is gone."""
    if not os.path.exists(POSITIONS_FILE):
        return []
    try:
        with open(POSITIONS_FILE) as f:
            saved = json.load(f)
    except (OSError, ValueError) as error:
        raise SystemExit(f"Could not read {POSITIONS_FILE}: {error}\n"
                         "Fix or move that file, then start the bot again.")
    positions = []
    for pos in saved:
        if os.path.exists(pos.get("open_path", "")):
            positions.append(pos)
        else:
            log(f"Skipping saved {pos.get('symbol')} position: {pos.get('open_path')} no longer exists")
    return positions


def get_pair(address):
    """Most liquid trading pair for a token address, or None."""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    pairs = [p for p in (response.json().get("pairs") or []) if p.get("chainId") == CHAIN]
    if not pairs:
        return None
    pairs.sort(key=lambda p: (p.get("liquidity") or {}).get("usd") or 0, reverse=True)
    return pairs[0]


def load_ticket(path):
    """Read a ticket file, fill in defaults, and check the numbers make sense."""
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("ticket must be a JSON object")
    address = data.get("token_address")
    if not isinstance(address, str) or len(address) < 20:
        raise ValueError("missing or invalid token_address")

    ticket = dict(DEFAULTS)
    ticket.update(data)
    get_strategy(ticket["strategy"])  # raises ValueError for a misspelled strategy name
    try:
        size = float(ticket["size_usd"])
        tp = float(ticket["take_profit_mult"])
        frac = float(ticket["sell_fraction_at_tp"])
        trail = float(ticket["trailing_stop_pct"])
        hard = float(ticket["hard_stop_pct"])
    except (TypeError, ValueError):
        raise ValueError("size and rule values must be numbers")
    if not 1 <= size <= 1000:
        raise ValueError("size_usd must be between 1 and 1000")
    if tp <= 1:
        raise ValueError("take_profit_mult must be above 1")
    if not 0 < frac <= 1:
        raise ValueError("sell_fraction_at_tp must be between 0 and 1")
    if not 0 < trail < 100 or not 0 < hard < 100:
        raise ValueError("stop percentages must be between 0 and 100")
    ticket.update(size_usd=size, take_profit_mult=tp, sell_fraction_at_tp=frac,
                  trailing_stop_pct=trail, hard_stop_pct=hard)
    return ticket


def reject(path, reason):
    name = os.path.basename(path)
    dest = os.path.join("orders/rejected", f"{int(time.time())}_{name}")
    shutil.move(path, dest)
    with open(dest + ".reason.txt", "w") as f:
        f.write(reason + "\n")
    log(f"REJECTED {name}: {reason}")


def handle_new_ticket(path, positions):
    name = os.path.basename(path)
    try:
        ticket = load_ticket(path)
    except (ValueError, OSError) as error:
        reject(path, f"Bad ticket: {error}")
        return

    try:
        pair = get_pair(ticket["token_address"])
    except requests.RequestException as error:
        log(f"Network problem reading {name}, will retry: {error}")
        return

    if pair is None or pair.get("priceUsd") is None:
        reject(path, f"No {CHAIN} trading pair or price found for that address")
        return

    strategy = ticket["strategy"]
    problems = [detail for reason, detail in check_token(pair, strategy)]
    if problems:
        reject(path, f"Failed {strategy} rules: " + "; ".join(problems))
        return

    symbol = (pair.get("baseToken") or {}).get("symbol")
    price = float(pair["priceUsd"])
    slip = SLIPPAGE_PCT / 100
    open_path = os.path.join("orders/open", f"{int(time.time())}_{name}")
    shutil.move(path, open_path)

    position = {
        "ticket": ticket,
        "open_path": open_path,
        "symbol": symbol,
        "start_price": price,
        "tokens": ticket["size_usd"] / (price * (1 + slip)),
        "peak": price,
        "last_price": price,
        "last_checked": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "took_profit": False,
        "cash": 0.0,
        "closed": False,
    }
    positions.append(position)
    log(f"PASSED {strategy} RULES. PAPER BUY ${ticket['size_usd']:.2f} of {label(position)} at ${price:.10f} "
        f"(sell {int(ticket['sell_fraction_at_tp'] * 100)}% at {ticket['take_profit_mult']}x, "
        f"{ticket['trailing_stop_pct']:.0f}% trailing stop, -{ticket['hard_stop_pct']:.0f}% hard stop)")


def update_position(pos):
    ticket = pos["ticket"]
    slip = SLIPPAGE_PCT / 100
    symbol = label(pos)

    try:
        pair = get_pair(ticket["token_address"])
    except requests.RequestException as error:
        log(f"{symbol}: network problem, will retry: {error}")
        return
    if pair is None or pair.get("priceUsd") is None:
        log(f"{symbol}: no price returned (token may be drained). Retrying...")
        return

    price = float(pair["priceUsd"])
    pos["peak"] = max(pos["peak"], price)
    pos["last_price"] = price  # saved to positions.json so export_results.py can show the "Now" multiple
    pos["last_checked"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    multiple = price / pos["start_price"]
    value = pos["tokens"] * price * (1 - slip)
    log(f"{symbol}: ${price:.10f} | {multiple:.2f}x | peak {pos['peak'] / pos['start_price']:.2f}x "
        f"| worth ${value:.2f}")

    def sell(fraction, reason):
        amount = pos["tokens"] * fraction
        proceeds = amount * price * (1 - slip)
        pos["cash"] += proceeds
        pos["tokens"] -= amount
        log(f"{symbol}: PAPER SELL {int(fraction * 100)}% at {multiple:.2f}x - {reason} "
            f"- got ${proceeds:.2f}")

    start = pos["start_price"]
    if not pos["took_profit"] and price <= start * (1 - ticket["hard_stop_pct"] / 100):
        sell(1.0, "HARD STOP-LOSS")
    elif not pos["took_profit"] and price >= start * ticket["take_profit_mult"]:
        sell(ticket["sell_fraction_at_tp"], "TAKE PROFIT")
        pos["took_profit"] = True
    elif pos["took_profit"] and price <= pos["peak"] * (1 - ticket["trailing_stop_pct"] / 100):
        sell(1.0, "TRAILING STOP")

    # If take-profit sold 100%, or a stop sold everything, the trade is over.
    if pos["tokens"] <= 1e-12:
        close_position(pos)


def close_position(pos):
    ticket = pos["ticket"]
    profit = pos["cash"] - ticket["size_usd"]
    done_path = os.path.join("orders/done", os.path.basename(pos["open_path"]))
    shutil.move(pos["open_path"], done_path)
    ticket["result"] = {
        "invested_usd": round(ticket["size_usd"], 2),
        "returned_usd": round(pos["cash"], 2),
        "profit_usd": round(profit, 2),
        "symbol": pos["symbol"],
        "strategy": ticket.get("strategy", DEFAULT_STRATEGY),
        "closed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    with open(done_path, "w") as f:
        json.dump(ticket, f, indent=2)
    log(f"{label(pos)}: TRADE CLOSED. In ${ticket['size_usd']:.2f}, "
        f"out ${pos['cash']:.2f}, profit/loss ${profit:+.2f}")
    pos["closed"] = True


def main():
    log("Ticket bot running in PAPER MODE (fake money). Drop tickets into the orders/ folder.")
    positions = load_positions()
    if positions:
        log(f"Picked up {len(positions)} saved paper position(s): "
            + ", ".join(label(p) for p in positions))
    log("Press Ctrl+C to stop.\n")
    try:
        while True:
            for path in sorted(glob.glob("orders/*.json")):
                handle_new_ticket(path, positions)
            for pos in positions[:]:
                update_position(pos)
                if pos["closed"]:
                    positions.remove(pos)
            save_positions(positions)
            time.sleep(CHECK_SECONDS)
    except KeyboardInterrupt:
        print()
        save_positions(positions)
        log(f"Stopped by you. {len(positions)} open paper position(s) saved to {POSITIONS_FILE}. "
            "They will be picked up again next time you start the bot.")


main()
