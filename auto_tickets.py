import json
import os
import time

from rules import DEFAULT_STRATEGY, STRATEGIES

MAX_PER_HOUR = 3      # per strategy
SIZE_USD = 20
SEEN_FILE = "seen_tokens.json"

os.makedirs("orders", exist_ok=True)

with open("data.json") as f:
    data = json.load(f)

seen = {}
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE) as f:
        seen = json.load(f)


# Older runs saved baseline tokens by bare address, so baseline keeps that and
# other strategies use "strategy:address". Token addresses never contain ":".
def seen_key(strategy, address):
    return address if strategy == DEFAULT_STRATEGY else f"{strategy}:{address}"


def strategy_of(key):
    return key.split(":")[0] if ":" in key else DEFAULT_STRATEGY


now = time.time()
made = 0

for strategy in STRATEGIES:
    recent = [k for k, t in seen.items() if strategy_of(k) == strategy and now - t < 3600]
    room = MAX_PER_HOUR - len(recent)
    count = 0
    for c in data["candidates"]:
        if count >= room:
            break
        # data.json files from before strategies existed only list baseline passers.
        if strategy not in c.get("strategies", [DEFAULT_STRATEGY]):
            continue
        key = seen_key(strategy, c["address"])
        if key in seen:
            continue
        ticket = {"token_address": c["address"], "size_usd": SIZE_USD, "strategy": strategy}
        with open(f"orders/auto_{strategy}_{int(now)}_{count}.json", "w") as f:
            json.dump(ticket, f)
        seen[key] = now
        count += 1
        made += 1
        print(f"{strategy}: ticket written for {c['symbol']}")

with open(SEEN_FILE, "w") as f:
    json.dump(seen, f)
print(f"{made} new ticket(s) this run.")
