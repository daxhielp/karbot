import os
from dotenv import load_dotenv
from analysis.analyzer import Analyzer


ENV = "demo"

# MAKE SURE .env IS CONFIGURED CORRECTLY
load_dotenv()
API_KEY_ID = os.getenv("KEYID") if ENV == "prod" else os.getenv("DEMO_KEYID")
API_KEY = os.getenv("KEYFILE") if ENV == "prod" else os.getenv("DEMO_KEYFILE")

client = Analyzer(API_KEY_ID, API_KEY)

batch = client.find_opportunities()
batch.print_batch()
