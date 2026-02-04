from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple
import time
import uuid

from kalshi.kalshi_client import KalshiClient
from analysis.opportunity import Opportunity
from execution.logger import ExecutionLogger

def retry_with_backoff(func, max_retries=3, base_delay=1):
    """
    Retry logic with exponential backoff.
    """
    last_exception = None
    for i in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if i < max_retries:
                time.sleep(base_delay * (2 ** i))
    raise last_exception

@dataclass
class Order:
    ticker: str
    side: str  # "yes" or "no"
    action: str  # "buy" or "sell"
    count: int
    price: float  # In dollars, e.g., 0.50
    order_type: str  # "market" or "limit"
    order_id: Optional[str] = None
    status: str = "pending"
    timestamp: datetime = datetime.now()

class Executor:
    """
    Class to perform order execution logic. Can run in dry, paper trade (experimental), or regular mode. 
    Dry mode simulates order filling 
    """

    def __init__(self, client: KalshiClient, config: dict = None):
        self.client = client
        self.config = config or {}
        self.dry_run = self.config.get("execution", {}).get("dry_run", True)
        self.paper_trading = self.config.get("execution", {}).get("paper_trading", False)
        
        # Initialize logger 
        log_filename = "paper_trading.jsonl" if self.paper_trading else "execution_log.jsonl"
        self.logger = ExecutionLogger(filename=log_filename)
        
        # Load thresholds from config or use defaults
        thresholds = self.config.get("execution", {}).get("thresholds", {})
        self.max_position_size_cents = thresholds.get("max_position_size_cents", 10000)
        self.min_profit_cents = thresholds.get("min_profit_cents", 5)
        
        # Timing configs
        timing = self.config.get("execution", {}).get("timing", {})
        self.execution_timeout = timing.get("execution_timeout_seconds", 60)
        self.poll_interval = timing.get("poll_interval_seconds", 2)
        self.retry_max = timing.get("retry_max_attempts", 3)
        self.retry_delay = timing.get("retry_base_delay_seconds", 1)

    def validate_execution(self, opportunity: Opportunity, quantity: int) -> Tuple[bool, str]:
        """
        Validates if an opportunity is safe and possible to execute.
        
        Checks:
        1. Account balance is sufficient
        2. Markets are active
        3. Prices haven't changed significantly (profit still exists)
        4. No markets expiring too soon
        """
        # 1. Refresh market data
        try:
            event_data = self.client.get_event(opportunity.event_ticker)
        except Exception as e:
            self.logger.log_validation(opportunity.event_ticker, False, f"Refresh failed: {e}")
            return False, f"Failed to refresh event data: {e}"
        
        # Map of ticker -> market_data for O(1) lookup
        fresh_markets_map = {m["ticker"]: m for m in event_data.get("markets", [])}

        
        current_total_cost_cents = 0
        
        # 2. Check each constituent market
        for market in opportunity.constituents:
            fresh_data = fresh_markets_map.get(market.ticker)
            
            if not fresh_data:
                self.logger.log_validation(opportunity.event_ticker, False, f"Market missing: {market.ticker}")
                return False, f"Market {market.ticker} no longer exists in event"
            
            if fresh_data.get("status") != "active":
                self.logger.log_validation(opportunity.event_ticker, False, f"Market inactive: {market.ticker}")
                return False, f"Market {market.ticker} is not active (status: {fresh_data.get('status')})"
            
            # Check for sufficient liquidity / price
            # Opportunity type "long" -> Buy Yes
            # Opportunity type "short" -> Buy No
            if opportunity.type == "long":
                price_cents = fresh_data.get("yes_ask")
            elif opportunity.type == "short":
                price_cents = fresh_data.get("no_ask")
            else:
                return False, f"Unknown opportunity type: {opportunity.type}"
                
            if price_cents is None:
                self.logger.log_validation(opportunity.event_ticker, False, f"No liquidity: {market.ticker}")
                return False, f"Market {market.ticker} has no liquidity for {opportunity.type}"
            
            current_total_cost_cents += price_cents
            
        current_total_cost_dollars = current_total_cost_cents / 100.0
        
        # 3. Check Profitability
        # Assuming typical arbitrage targets < $1.00 total cost for $1.00 payout
        if current_total_cost_dollars >= 1.0:
            self.logger.log_validation(opportunity.event_ticker, False, f"Not profitable: cost {current_total_cost_dollars}")
            return False, f"Opportunity no longer profitable: cost is ${current_total_cost_dollars:.2f}"
            
        # Check against min profit if cost increased
        # Expected profit per contract = $1.00 - cost
        expected_profit_cents = 100 - current_total_cost_cents
        if expected_profit_cents < self.min_profit_cents:
             self.logger.log_validation(opportunity.event_ticker, False, f"Low profit: {expected_profit_cents}c")
             return False, f"Profit {expected_profit_cents}c is below minimum {self.min_profit_cents}c"

        # 4. Check Balance
        required_amount = current_total_cost_dollars * quantity
        
        # Ensure we don't exceed max position size
        if (required_amount * 100) > self.max_position_size_cents:
            self.logger.log_validation(opportunity.event_ticker, False, "Exceeds max position size")
            return False, f"Order cost {required_amount * 100}c exceeds max position size {self.max_position_size_cents}c"
        
        try:
            current_balance = self.client.get_balance()
        except Exception as e:
            return False, f"Failed to fetch balance: {e}"
            
        if current_balance < required_amount:
            self.logger.log_validation(opportunity.event_ticker, False, "Insufficient balance")
            return False, f"Insufficient balance: ${current_balance:.2f} < ${required_amount:.2f}"

        self.logger.log_validation(opportunity.event_ticker, True)
        return True, ""

    def create_orders_from_opportunity(self, opportunity: Opportunity, quantity: int, action: str = "buy", refresh_prices: bool = True) -> List[Order]:
        orders = []
        fresh_markets_map = {}
        
        if refresh_prices:
            try:
                event_data = self.client.get_event(opportunity.event_ticker)
                fresh_markets_map = {m["ticker"]: m for m in event_data.get("markets", [])}
            except Exception as e:
                print(f"Warning: Could not refresh prices: {e}")
                # Fallback to not refreshing prices if fetching fails
                refresh_prices = False

        for market in opportunity.constituents:
            price = 0.0
            side = ""
            
            # Use fresh data if available
            if refresh_prices and market.ticker in fresh_markets_map:
                m_data = fresh_markets_map[market.ticker]
                if action == "sell":
                    if opportunity.type == "long":
                        price = m_data.get("yes_bid", 0) / 100.0
                        side = "yes"
                    else:
                        price = m_data.get("no_bid", 0) / 100.0
                        side = "no"
                else:
                    if opportunity.type == "long":
                        price = m_data.get("yes_ask", 0) / 100.0
                        side = "yes"
                    else:
                        price = m_data.get("no_ask", 0) / 100.0
                        side = "no"
            else:
                if action == "sell":
                    price = 0.01 # Fallback
                    if opportunity.type == "long":
                        side = "yes"
                    else:
                        side = "no"
                else:
                    if opportunity.type == "long":
                        price = market.yes_ask
                        side = "yes"
                    else:
                        price = market.no_ask
                        side = "no"
            
            orders.append(Order(
                ticker=market.ticker,
                side=side,
                action=action,
                count=quantity,
                price=price,
                order_type="limit"
            ))
            
        return orders

    def create_orders_from_positions(self, positions: List[dict], quantity: int = None) -> List[Order]:
        """
        Creates sell orders for the given positions.
        """
        orders = []
        for pos in positions:
            t = pos.get("market_ticker") or pos.get("ticker")
            s = pos.get("side", "yes")
            c = pos.get("position") if "position" in pos else pos.get("count", 0)
            
            if quantity:
                c = min(c, quantity)
            
            if c <= 0: continue

            price = 0.05
            try:
                m = self.client.get_market(t)
                if s == "yes":
                    price = m.get("yes_bid", 0) / 100.0
                else:
                    price = m.get("no_bid", 0) / 100.0
            except Exception:
                pass
                
            orders.append(Order(
                ticker=t,
                side=s,
                action="sell",
                count=c,
                price=price,
                order_type="limit"
            ))
        return orders

    def execute_orders(self, orders: List[Order]) -> dict:
        self.logger.log_execution("unknown_opp", orders) # Opportunity ticker not passed here, could improve
        
        if self.paper_trading or self.dry_run:
            mode = "PAPER TRADING" if self.paper_trading else "DRY RUN"
            print(f"[{mode}] Simulating execution...")
            submitted_orders = []
            for order in orders:
                order.order_id = f"paper_{uuid.uuid4().hex[:8]}"
                order.status = "submitted"
                submitted_orders.append(order.order_id)
            return {
                "total_submitted": len(orders),
                "successful_submissions": len(orders),
                "failed_submissions": 0,
                "order_ids": submitted_orders
            }
            
        # Convert Orders to API dicts
        api_orders = []
        for order in orders:
            # API expects: ticker, action, side, count, type, yes_price/no_price
            # For 'buy', we specify max price we are willing to pay?
            # Kalshi API:
            # action: 'buy' or 'sell'
            # side: 'yes' or 'no'
            # count: int
            # type: 'limit' or 'market (only limit currently supported)
            # yes_price: int (cents) if side yes
            # no_price: int (cents) if side no
            
            api_order = {
                "ticker": order.ticker,
                "action": order.action,
                "side": order.side,
                "count": order.count,
                "type": order.order_type,
                "client_order_id": str(uuid.uuid4())
            }
            
            price_cents = int(order.price * 100)
            if order.side == "yes":
                api_order["yes_price"] = price_cents
            else:
                api_order["no_price"] = price_cents
                
            api_orders.append(api_order)
            
        # Execute batch with retry
        responses = []
        try:
            responses = retry_with_backoff(
                lambda: self.client.place_orders(api_orders),
                max_retries=self.retry_max,
                base_delay=self.retry_delay
            )
        except Exception as e:
            print(f"Failed to place orders after retries: {e}")
            for order in orders:
                order.status = "failed"
            return {
                "total_submitted": len(orders),
                "successful_submissions": 0,
                "failed_submissions": len(orders),
                "order_ids": []
            }
        
        successful = 0
        failed = 0
        order_ids = []
        
        # Update Order objects with results
        for i, resp in enumerate(responses):
            order = orders[i]
            if "order_id" in resp:
                order.order_id = resp["order_id"]
                order.status = resp.get("status", "submitted")
                order_ids.append(order.order_id)
                successful += 1
            elif "order" in resp and "order_id" in resp["order"]:
                 order.order_id = resp["order"]["order_id"]
                 order.status = resp["order"].get("status", "submitted")
                 order_ids.append(order.order_id)
                 successful += 1
            else:
                order.status = "failed"
                # Log error from response
                print(f"Order failed for {order.ticker}: {resp.get('error', 'Unknown error')}")
                failed += 1
                
        return {
            "total_submitted": len(orders),
            "successful_submissions": successful,
            "failed_submissions": failed,
            "order_ids": order_ids
        }

    def monitor_orders(self, orders: List[Order], progress_callback=None) -> dict:
        """
        Polls order status until all filled or timeout.
        """
        start_time = time.time()
        order_ids = [o.order_id for o in orders if o.order_id and o.status != "failed"]
        
        if not order_ids:
            return {"all_filled": False, "filled_orders": [], "pending_orders": []}

        if self.paper_trading:
            while (time.time() - start_time) < self.execution_timeout:
                all_filled = True
                for order in orders:
                    if order.status in ["filled", "canceled", "failed"]:
                        continue
                    
                    all_filled = False
                    try:
                        # Refresh market data to simulate matching
                        m = self.client.get_market(order.ticker)
                        
                        should_fill = False
                        
                        if order.action == "sell":
                             # Selling: We need a Bid >= our Limit Price
                             bid = m.get("yes_bid") if order.side == "yes" else m.get("no_bid")
                             if bid is not None:
                                 bid_price = bid / 100.0
                                 if bid_price >= order.price:
                                     should_fill = True
                        else:
                             # Buying: We need an Ask <= our Limit Price
                             ask = m.get("yes_ask") if order.side == "yes" else m.get("no_ask")
                             if ask is not None:
                                 ask_price = ask / 100.0
                                 if ask_price <= order.price:
                                     should_fill = True

                        if should_fill:
                             order.status = "filled"
                             self.logger.log_fill(order.order_id, order.ticker, order.count, order.price)
                    except Exception as e:
                        # Log/print error but don't crash loop
                        print(f"Paper trading monitor error: {e}")
                
                # Update progress
                filled = [o for o in orders if o.status == "filled"]
                pending = [o for o in orders if o.status == "submitted"]
                if progress_callback:
                    progress_callback(filled, pending)
                    
                if all_filled:
                    break
                time.sleep(self.poll_interval)
            
            filled = [o for o in orders if o.status == "filled"]
            pending = [o for o in orders if o.status == "submitted"]
            return {
                "all_filled": len(pending) == 0,
                "filled_orders": filled,
                "pending_orders": pending,
                "execution_time": time.time() - start_time
            }

        if self.dry_run:
            # Simulate fills
            time.sleep(1) # Fake delay
            for o in orders:
                if o.status == "submitted":
                    o.status = "filled"
                    self.logger.log_fill(o.order_id, o.ticker, o.count, o.price)
            if progress_callback:
                progress_callback(orders, [])
            return {"all_filled": True, "filled_orders": orders, "pending_orders": [], "execution_time": 1.0}

        while (time.time() - start_time) < self.execution_timeout:
            all_filled = True
            
            for order in orders:
                if order.status in ["filled", "canceled", "failed"]:
                    continue
                
                # Check status with retry
                try:
                    status_resp = retry_with_backoff(
                        lambda: self.client.get_order_status(order.order_id),
                        max_retries=self.retry_max,
                        base_delay=self.retry_delay
                    )
                    
                    # Check for 'order' key if nested
                    data = status_resp.get("order", status_resp)
                    new_status = data.get("status")
                    
                    if new_status:
                        order.status = new_status
                        
                        if new_status == "executed":
                            # Log fill
                            self.logger.log_fill(order.order_id, order.ticker, order.count, order.price)
                        elif new_status == "canceled":
                            pass
                        else:
                            all_filled = False
                    else:
                        all_filled = False # Couldn't get status
                except Exception as e:
                    print(f"Failed to check status for {order.order_id}: {e}")
                    all_filled = False
            
            filled = [o for o in orders if o.status == "executed" or o.status == "filled"]
            pending = [o for o in orders if o.status not in ["executed", "filled", "canceled", "failed"]]
            if progress_callback:
                progress_callback(filled, pending)
            
            if all_filled:
                break
                
            time.sleep(self.poll_interval)
            
        filled = [o for o in orders if o.status == "executed" or o.status == "filled"] # Kalshi uses 'executed' 
        pending = [o for o in orders if o.status not in ["executed", "filled", "canceled", "failed"]]
        
        self.logger.log_monitor_summary(filled, pending, time.time() - start_time)
        
        return {
            "all_filled": len(pending) == 0,
            "filled_orders": filled,
            "pending_orders": pending,
            "execution_time": time.time() - start_time
        }

    def rollback_orders(self, orders: List[Order]) -> dict:
        """
        Attempts to cancel pending orders.
        """
        results = {}
        to_cancel = [o for o in orders if o.status not in ["executed", "filled", "canceled", "failed"] and o.order_id]
        
        if self.paper_trading or self.dry_run:
             mode = "PAPER TRADING" if self.paper_trading else "DRY RUN"
             print(f"[{mode}] Rolling back orders...")
             for o in to_cancel:
                o.status = "canceled"
                results[o.order_id] = True
             return {"successful_cancellations": len(to_cancel), "failed_cancellations": 0}
            
        success_count = 0
        failed_count = 0
        
        for order in to_cancel:
            try:
                success = self.client.cancel_order(order.order_id)
                results[order.order_id] = success
                if success:
                    order.status = "canceled"
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                print(f"Error canceling {order.order_id}: {e}")
                results[order.order_id] = False
                failed_count += 1
                
        self.logger.log_rollback([o.order_id for o in to_cancel], results)
        
        return {
            "successful_cancellations": success_count,
            "failed_cancellations": failed_count
        }
