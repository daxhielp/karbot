from datetime import datetime, timedelta
import time
from kalshi.kalshi_client import KalshiClient


class Karbot(KalshiClient):
    """
    A Kalshi-Arbitrage-Bot implemented as a subclass of the KalshiClient class.
    This class is specialzied with arbitrage 
    """
    def get_market_arbitrage(self, title: str, markets: list) -> list:
        """
        Analyzes the event markets for arbitrage opportunities across the entire event.
        Checks for:
        1. Single market arbitrage (Yes + No < 100)
        2. Mutually exclusive arbitrage (Sum of Yes < 100)
        3. Mutually exclusive short arbitrage (Sum of No < (N-1)*100)
        
        :param markets: List of market dictionaries to analyze from a single event
        """
        opportunities = []
        
        # collect prices for event-level analysis
        yes_asks = []
        no_asks = []
        tickers = []
        
        for market in markets:
            yes_ask = market.get("yes_ask")
            no_ask = market.get("no_ask")
            ticker = market.get("ticker")

            int 

            if not yes_ask or not no_ask:
                continue

            if yes_ask:
                yes_asks.append(yes_ask)
            if no_ask:
                no_asks.append(no_ask)
            tickers.append(ticker)

            # single Market Arbitrage (Yes + No < 100)
            if yes_ask and no_ask:
                total_cost = yes_ask + no_ask
                if total_cost < 100:
                    opportunity = {
                        "title": title,
                        "market_ticker": ticker,
                        "type": "single_market",
                        "yes_ask": yes_ask,
                        "no_ask": no_ask,
                        "total_cost": total_cost,
                        "profit": 100 - total_cost
                    }
                    opportunities.append(opportunity)
        
        # ensure we have at least 2 markets for cross-market arb
        if len(markets) < 2:
            return opportunities

        # 1. Event Bundle (Long) - Buy Yes on all outcomes
        if len(yes_asks) == len(tickers):
            total_yes_cost = sum(yes_asks)
            if total_yes_cost < 100:
                opportunity = {
                    "title": title,
                    "market_ticker": f"Event Bundle Long ({markets[0].get('event_ticker', 'Unknown')})",
                    "type": "bundle_long",
                    "total_cost": total_yes_cost,
                    "profit": 100 - total_yes_cost,
                    "constituents": tickers
                }
                opportunities.append(opportunity)

        # 2. Event Bundle (Short) - Buy No on all outcomes
        # win condition: one Yes wins (payoff 0 for that No), others lose (payoff 100 for those Nos)
        # total Payout = (N-1) * 100
        if len(no_asks) == len(tickers):
            total_no_cost = sum(no_asks)
            payout = (len(tickers) - 1) * 100
            if total_no_cost < payout:
                opportunity = {
                    "title": title,
                    "market_ticker": f"Event Bundle Short ({tickers[0].get('event_ticker', 'Unknown')})",
                    "type": "bundle_short",
                    "total_cost": total_no_cost,
                    "profit": payout - total_no_cost,
                    "constituents": tickers
                }
                opportunities.append(opportunity)
                
        return opportunities

    def process_event(self, event: dict) -> list:
        title = event.get("title")
        raw_markets = event.get("markets", [])
        mutually_exclusive = event.get("mutually_exclusive", False)
        
        if not mutually_exclusive or not raw_markets:
            return []

        try:
            # TODO: can change to filtered/unfiltered
            return self.get_market_arbitrage(title, raw_markets)
        except Exception as e:
            ticker = event.get("event_ticker", "unknown")
            print(f"Error exploring arbitrage for {ticker}: {e}")
                
        return []

    def get_batch_arbitrage(self, limit: int=20) -> list:
        """
        Analyzes a batch of Kalshi events and finds choices optimal for arbitrage.
        
        :param limit: Desired number of events
        :type limit: int
        :return: A list of all markets optimal for arbitrage, unrelated to their event
        :rtype: list
        """
        events_data = self.get_events(limit=limit)
        events = events_data.get("events", [])
        
        all_opportunities = []
        for event in events:
            opportunities = self.process_event(event)
            all_opportunities.extend(opportunities)
                    
        return all_opportunities

    def find_opportunities(self, target_amount: int=5) -> list:
        """
        Continuously searches markets until the target amount of arbitrage opportunities is found.
        Handles pagination and rate limiting.
        """
        all_opportunities = []
        cursor = None
        
        while len(all_opportunities) < target_amount:
            # Respect read limit
            # Default to 1 second sleep if limit is unknown or 0, otherwise 1.1/limit
            sleep_time = 1.0
            if hasattr(self, 'read_limit') and self.read_limit > 0:
                sleep_time = 1.1 / self.read_limit
            time.sleep(sleep_time)

            params = {}
            if cursor:
                params['cursor'] = cursor
            
            # batch size of 100 for efficiency
            events_data = self.get_events(limit=100, **params)
            events = events_data.get("events", [])
            cursor = events_data.get("cursor")
            
            if not events:
                break
                
            for event in events:
                opportunities = self.process_event(event)
                all_opportunities.extend(opportunities)
                if len(all_opportunities) >= target_amount:
                    break
            
            if not cursor:
                break
                
        return all_opportunities