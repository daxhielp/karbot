from kalshi.kalshi_client import KalshiClient
import uuid

class MockKalshiClient(KalshiClient):
    def __init__(self, env="demo"):
        self.env = env
        self.orders = {}
        self.balance = 10000.0 # $10,000
        self.write_limit = 100
        
    def get_event(self, ticker, with_nested_markets=True):
        # Return dummy event
        # Assuming ticker is like "TEST"
        return {
            "ticker": ticker,
            "markets": [
                {"ticker": f"{ticker}-M1", "status": "active", "yes_ask": 50, "no_ask": 50, "expiration_time": "2025-01-01T00:00:00Z"},
                {"ticker": f"{ticker}-M2", "status": "active", "yes_ask": 40, "no_ask": 60, "expiration_time": "2025-01-01T00:00:00Z"}
            ]
        }
        
    def get_market(self, ticker):
        return {"ticker": ticker, "status": "active", "yes_ask": 50, "no_ask": 50}
        
    def get_balance(self):
        return self.balance
        
    def place_orders(self, orders: list[dict]) -> list[dict]:
        responses = []
        for o in orders:
            order_id = str(uuid.uuid4())
            self.orders[order_id] = {
                "order_id": order_id,
                "status": "submitted", 
                "ticker": o["ticker"],
                "count": o["count"],
                "side": o["side"]
            }
            responses.append({"order_id": order_id, "status": "submitted"})
        return responses
        
    def get_order_status(self, order_id: str) -> dict:
        if order_id in self.orders:
            # Simulate fill on check
            # self.orders[order_id]["status"] = "executed"
            return {"order": self.orders[order_id]}
        return {"error": "Not found"}
        
    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            self.orders[order_id]["status"] = "canceled"
            return True
        return False
