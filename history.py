import json
import os

with open("data.json") as f:
    data = json.load(f)

history = []
if os.path.exists("history.json"):
    with open("history.json") as f:
        history = json.load(f)

if not history or history[-1].get("updated") != data["updated"]:
    tokens = []
    for c in data["candidates"][:15]:
        try:
            price = float(c["price_usd"])
        except (TypeError, ValueError):
            continue
        tokens.append({"address": c["address"], "symbol": c["symbol"], "price": price})
    history.append({
        "updated": data["updated"],
        "scanned": data["scanned"],
        "passed": data["passed"],
        "tokens": tokens,
    })

history = history[-400:]
with open("history.json", "w") as f:
    json.dump(history, f)
print(f"History has {len(history)} scans.")
