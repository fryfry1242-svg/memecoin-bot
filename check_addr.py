import sys
import requests

address = sys.argv[1]
base = "https://api.dexscreener.com/latest/dex"

as_token = requests.get(f"{base}/tokens/{address}", timeout=10).json().get("pairs") or []
as_pair = requests.get(f"{base}/pairs/solana/{address}", timeout=10).json().get("pairs") or []

if as_token:
    print("This is a TOKEN address. It works with the bot.")
elif as_pair:
    token = as_pair[0]["baseToken"]
    print("That is a PAIR address, not a token address.")
    print(f"The token address for {token['symbol']} is:")
    print(token["address"])
else:
    print("Not found on Solana. Wrong chain, or a typo in the address.")
