import glob
import json
import os
from datetime import datetime, timezone

# Reads the ticket bot's private files and writes a summary for the dashboard's Paper trades tab.
POSITIONS_FILE = "positions.json"   # open paper trades, saved by ticket_bot.py
DONE_FOLDER = "orders/done"         # one file per closed paper trade
OUT_FILE = "paper.json"


def short_address(address):
    return address[:6] + "..." if isinstance(address, str) else "?"


def load_open():
    """Open paper trades from positions.json."""
    if not os.path.exists(POSITIONS_FILE):
        return []
    try:
        with open(POSITIONS_FILE) as f:
            saved = json.load(f)
    except (OSError, ValueError) as error:
        raise SystemExit(f"Could not read {POSITIONS_FILE}: {error}")
    rows = []
    for pos in saved:
        ticket = pos.get("ticket") or {}
        start = pos.get("start_price") or 0
        rows.append({
            "symbol": pos.get("symbol") or short_address(ticket.get("token_address")),
            "address": ticket.get("token_address"),
            "invested_usd": round(float(ticket.get("size_usd") or 0), 2),
            "start_price": start,
            "peak_mult": round(pos.get("peak", start) / start, 2) if start else None,
            "took_profit": bool(pos.get("took_profit")),
            "cash_taken_usd": round(float(pos.get("cash") or 0), 2),
        })
    return rows


def load_closed():
    """Closed paper trades from orders/done/. Files that can't be read are skipped and counted."""
    rows = []
    skipped = 0
    for path in glob.glob(os.path.join(DONE_FOLDER, "*.json")):
        try:
            with open(path) as f:
                ticket = json.load(f)
            result = ticket["result"]
            row = {
                "symbol": result.get("symbol") or short_address(ticket.get("token_address")),
                "address": ticket.get("token_address"),
                "invested_usd": float(result["invested_usd"]),
                "returned_usd": float(result["returned_usd"]),
                "profit_usd": float(result["profit_usd"]),
                # Older files have no closed_at, so fall back to when the file was last written.
                "closed_at": result.get("closed_at") or datetime.fromtimestamp(
                    os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            }
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            skipped += 1
            continue
        rows.append(row)
    rows.sort(key=lambda r: r["closed_at"], reverse=True)
    return rows, skipped


def make_totals(open_rows, closed):
    profits = [c["profit_usd"] for c in closed]
    total = sum(profits)
    wins = sum(1 for p in profits if p > 0)
    best = max(closed, key=lambda c: c["profit_usd"]) if closed else None
    return {
        "closed_trades": len(closed),
        "wins": wins,
        "losses": len(closed) - wins,
        "win_rate_pct": round(wins / len(closed) * 100, 1) if closed else None,
        "invested_usd": round(sum(c["invested_usd"] for c in closed), 2),
        "returned_usd": round(sum(c["returned_usd"] for c in closed), 2),
        "profit_usd": round(total, 2),
        "best_trade": {"symbol": best["symbol"], "profit_usd": best["profit_usd"]} if best else None,
        # Would we still be up without our single luckiest trade? Needs 2+ trades to mean anything.
        "profit_without_best_usd": round(total - best["profit_usd"], 2) if len(closed) >= 2 else None,
        "open_trades": len(open_rows),
        "open_invested_usd": round(sum(o["invested_usd"] for o in open_rows), 2),
    }


def main():
    open_rows = load_open()
    closed, skipped = load_closed()
    result = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "open": open_rows,
        "closed": closed,
        "skipped_files": skipped,
        "totals": make_totals(open_rows, closed),
    }
    with open(OUT_FILE, "w") as f:
        json.dump(result, f, indent=2)
    t = result["totals"]
    print(f"{len(open_rows)} open, {len(closed)} closed paper trade(s). "
          f"Total profit ${t['profit_usd']:+.2f}. Wrote {OUT_FILE}.")
    if skipped:
        print(f"Skipped {skipped} file(s) in {DONE_FOLDER} that could not be read.")


main()
