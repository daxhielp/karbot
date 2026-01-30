import os
from dotenv import load_dotenv
from karbot_client import Karbot


ENV = "demo"

load_dotenv()
API_KEY_ID = os.getenv("KEYID") if ENV == "prod" else os.getenv("DEMO_KEYID")
API_KEY = os.getenv("KEYFILE") if ENV == "prod" else os.getenv("DEMO_KEYFILE")

client = Karbot(API_KEY_ID, API_KEY, env=ENV)

balance = client.get_balance()
print(f"Balance: ${balance:.2f}")


event = client.get_event("SENATESD-28", True)
# print(event)
markets = event.get("markets")
for m in markets:
    title = m.get("title")
    yes_ask = m.get("yes_ask")
    no_ask = m.get("no_ask")

    print(f"{title}")
    print(f"yes: {yes_ask}")
    print(f"no: {no_ask}")


# prospects = client.find_opportunities(target_amount=5)
# for i, m in enumerate(prospects):
#     print()
#     print(f"Opportunity {i + 1}: {m.get("market_ticker")}")
#     print(f"Event title: {m.get("title")}")

#     cost = m.get("total_cost") / 100
#     profit = m.get("profit") / 100
#     print(f"Expected cost for at-price bid: ${cost:.2f}")
#     print(f"Expected profit for at-price bid: ${profit:.2f}")
