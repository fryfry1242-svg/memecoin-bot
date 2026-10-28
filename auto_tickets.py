import json
import os
import time

MAX_PER_HOUR = 3
SIZE_USD = 20
SEEN_FILE = "seen_tokens.json"

os.makedirs("orders", exist_ok=True)

with open("data.json") as f:
    data = json.load(f)

seen = {}
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE) as f:
        seen = json.load(f)

now = time.time()
recent = [a for a, t in seen.items() if now - t < 3600]
room = MAX_PER_HOUR - len(recent)
made = 0

for c in data["candidates"]:
    if made >= room:
        break
    address = c["address"]
    if address in seen:
        continue
    ticket = {"token_address": address, "size_usd": SIZE_USD}
    with open(f"orders/auto_{int(now)}_{made}.json", "w") as f:
        json.dump(ticket, f)
    seen[address] = now
    made += 1
    print(f"Ticket written for {c['symbol']}")

with open(SEEN_FILE, "w") as f:
    json.dump(seen, f)
print(f"{made} new ticket(s) this run.")
