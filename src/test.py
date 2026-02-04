from kalshi.kalshi_client import KalshiClient
import os
from dotenv import load_dotenv

ENV = "demo"

load_dotenv()
API_KEY_ID = os.getenv("KEYID") if ENV == "prod" else os.getenv("DEMO_KEYID")
API_KEY = os.getenv("KEYFILE") if ENV == "prod" else os.getenv("DEMO_KEYFILE")

client = KalshiClient(API_KEY_ID, API_KEY, env=ENV)

positions = client.get_positions()
print(positions)
