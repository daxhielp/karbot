import unittest
from tests.mock_client import MockKalshiClient
from execution.executor import Executor, Order
from analysis.opportunity import Opportunity
from analysis.market import Market

class TestExecutor(unittest.TestCase):
    def setUp(self):
        self.client = MockKalshiClient()
        # Ensure we disable dry_run to test "real" logic against mock client
        self.executor = Executor(self.client, config={"execution": {"dry_run": False}})
        
    def test_create_orders(self):
        # Create dummy opp
        m1 = Market("TEST-M1", 50, 50, "2025-01-01T00:00:00Z")
        # Opportunity needs to be constructed carefully
        opp = Opportunity("Test Opp", "TEST", "long", 100, 0, [m1])
        
        # We disable refresh_prices to avoid needing get_event result to match exactly in this simple test
        orders = self.executor.create_orders_from_opportunity(opp, 1, refresh_prices=False)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].ticker, "TEST-M1")
        self.assertEqual(orders[0].side, "yes")
        
    def test_execute_orders(self):
        o1 = Order("TEST-M1", "yes", "buy", 1, 0.50, "limit")
        res = self.executor.execute_orders([o1])
        self.assertEqual(res["successful_submissions"], 1)
        self.assertIsNotNone(o1.order_id)
        self.assertEqual(o1.status, "submitted")
        
    def test_monitor_orders(self):
        o1 = Order("TEST-M1", "yes", "buy", 1, 0.50, "limit")
        res = self.executor.execute_orders([o1])
        
        # Manually fill in mock
        self.client.orders[o1.order_id]["status"] = "executed"
        
        res_mon = self.executor.monitor_orders([o1])
        self.assertTrue(res_mon["all_filled"])
        self.assertEqual(o1.status, "executed")
        
if __name__ == '__main__':
    unittest.main()
