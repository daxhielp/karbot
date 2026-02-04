import json
import os
import datetime

class ExecutionLogger:
    def __init__(self, log_dir: str = None, filename: str = "execution_log.jsonl"):
        # If no log_dir specified, use root/logs
        if log_dir is None:
            # Get the project root (3 levels up from this file: src/execution/logger.py)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            log_dir = os.path.join(project_root, "logs")
        

        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.log_file = os.path.join(log_dir, filename)
        
    def _log(self, action: str, status: str, details: dict):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "action": action,
            "status": status,
            "details": details
        }
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"Failed to write to execution log: {e}")
            
    def log_validation(self, opportunity_ticker: str, success: bool, reason: str = ""):
        self._log("validate", "success" if success else "failed", {
            "opportunity": opportunity_ticker,
            "reason": reason
        })

    def log_execution(self, opportunity_ticker: str, orders: list):
        # serialize orders - orders is list of Order objects
        order_details = []
        for o in orders:
            order_details.append({
                "ticker": o.ticker, 
                "action": o.action, 
                "side": o.side,
                "count": o.count,
                "price": o.price
            })
            
        self._log("execute", "submitted", {
            "opportunity": opportunity_ticker,
            "order_count": len(orders),
            "orders": order_details
        })
        
    def log_fill(self, order_id: str, ticker: str, filled_count: int, price: float):
        self._log("fill", "filled", {
            "order_id": order_id,
            "ticker": ticker,
            "count": filled_count,
            "price": price
        })
        
    def log_rollback(self, order_ids: list, success_map: dict):
         self._log("rollback", "completed", {
             "order_ids": order_ids,
             "results": success_map
         })
         
    def log_monitor_summary(self, filled: list, pending: list, execution_time: float):
        self._log("monitor", "summary", {
            "filled_count": len(filled),
            "pending_count": len(pending),
            "execution_time_seconds": execution_time
        })
