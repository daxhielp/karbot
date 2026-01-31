import os
from dotenv import load_dotenv
from analyzer import Analyzer, Opportunity, Market


ENV = "demo"

# load api keys
load_dotenv()
API_KEY_ID = os.getenv("KEYID") if ENV == "prod" else os.getenv("DEMO_KEYID")
API_KEY = os.getenv("KEYFILE") if ENV == "prod" else os.getenv("DEMO_KEYFILE")


def print_market(market: Market, type: str):
    print(f"Market: {market.ticker}")
    cost = market.yes_ask if type == "long" else market.no_ask
    print(f"Cost of entry per contract: {cost}")
    print(f"Expiration date: {market.exp_date}")
    print()

def print_markets(event: Opportunity, limit: int=10):
    print()
    print("Markets:")
    printed = 0
    for m in event.constituents:
        if printed == limit and limit != 0:
            print("...")
            break
        print_market(m, e.type)
        printed += 1
    print()


# create client instance
client = Analyzer(API_KEY_ID, API_KEY, env=ENV)

# check balance
balance = client.get_balance()
print(f"Balance: ${balance:.2f}")
print()

# find and display opportunities
prospects = client.find_opportunities(target_amount=10)
for i, e in enumerate(prospects):
    print()
    print(f"---------------------- Opportunity {i + 1}: {e.event_ticker} ----------------------")
    print(e.title)

    cost = e.total_cost / 100
    profit = e.profit / 100
    print(f"Expected total cost for at-price bid: ${cost:.2f}")
    print(f"Expected profit for at-price bid: ${profit:.2f}")

    print_markets(e, 0)
