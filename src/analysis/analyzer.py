from datetime import datetime, timedelta
import time
import tqdm

from kalshi.kalshi_client import KalshiClient
from .market import Market
from .opportunity import Opportunity
from .batch import Batch



class Analyzer(KalshiClient):
    """
    A Kalshi-Arbitrage-Bot implemented as a subclass of the KalshiClient class.
    This class is specialzied with algorithms and functions for arbitrage and 
    """
    def get_market_arbitrage(self, title: str, markets: list) -> list[Opportunity]:
        """
        Analyzes the event markets for arbitrage opportunities across the entire event.
        Outcomes can either be a 'bundle long' or 'bundle sort'
        Checks for:
        1. Mutually exclusive 'long' arbitrage (Sum of Yes < 100)
        2. Mutually exclusive 'short' arbitrage (Sum of No < (N-1)*100)
        
        :param markets: List of market dictionaries to analyze from a single event
        """
        opportunities = []
        
        # collect prices for event-level analysis
        yes_asks, no_asks, valid_markets = self._prep_markets(markets)

        # ensure we have at least 2 markets for cross-market arb
        if len(valid_markets) < 2:
            return opportunities

        
        event_ticker = markets[0].get("event_ticker", "Unknwon")
        # 1. Event Bundle (Long) - Buy Yes on all outcomes
        if len(yes_asks) == len(valid_markets):
            total_yes_cost = sum(yes_asks)
            if total_yes_cost < 100:

                opportunity = Opportunity(
                    title=title,
                    event_ticker=event_ticker,
                    type="long",
                    total_cost=total_yes_cost,
                    profit=100 - total_yes_cost,
                    constituents=valid_markets
                )
                opportunities.append(opportunity)

        # 2. Event Bundle (Short) - Buy No on all outcomes
        # win condition: one Yes wins (payoff 0 for that No), others lose (payoff 100 for those Nos)
        if len(no_asks) == len(valid_markets):
            total_no_cost = sum(no_asks)
            # total Payout = (N-1) * 100
            payout = (len(valid_markets) - 1) * 100
            if total_no_cost < payout:
                opportunity = Opportunity(
                    title=title,
                    event_ticker=event_ticker,
                    type="short",
                    total_cost=total_no_cost,
                    profit=payout - total_no_cost,
                    constituents=valid_markets
                )
                opportunities.append(opportunity)
                
        return opportunities

    def _prep_markets(self, markets: list[dict]) -> tuple[list[int], list[int], list[Market]]:
        """
        Extract all valid markets and their respective yes/no asks
        
        :param markets: list of markets to 
        :type markets: list[dict]
        :return: Description
        :rtype: tuple[list[int], list[int], list[str]]
        """
        yes_asks = []
        no_asks = []
        valid_markets = []
        
        for market in markets:
            if not self._valid_market(market, "yes") or not self._valid_market(market, "no"):
                continue

            ticker = market.get("ticker")
            yes_ask = market.get("yes_ask")
            no_ask = market.get("no_ask")
            exp_date = market.get("expiration_time")
            valid_market = Market(
                ticker=ticker,
                yes_ask=yes_ask,
                no_ask=no_ask,
                exp_date=exp_date
            )

            yes_asks.append(yes_ask)
            no_asks.append(no_ask)


            valid_markets.append(valid_market)

        return yes_asks, no_asks, valid_markets

    def _valid_market(self, market: dict, ask_type: str) -> bool:
        """
        Determine if a market is valid for arbitrage
        
        :param market: Kalshi market object
        :type market: dict
        :param ask_type: 'yes' or 'no'
        :type type: str
        :return: True if market is currently active and has valid ask prices for both yes and no. False otherwise
        :rtype: bool
        """
        ask = market.get(f"{ask_type}_ask")
        status = market.get("status")

        if status != "active":
            return False

        if ask <= 0 or ask >= 100:
            return False
        
        return True

    def process_event(self, event: dict) -> list[Opportunity]:
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

    def get_batch_arbitrage(self, limit: int=20) -> list[Opportunity]:
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

    def find_opportunities(self, target_amount: int=5) -> Batch:
        """
        Continuously searches markets until the target amount of arbitrage opportunities is found.
        Handles pagination and rate limiting.
        """
        all_opportunities = []
        cursor = None
        
        with tqdm.tqdm(total=target_amount, desc="Finding opportunities", unit="opp") as pbar:
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
                    if opportunities:
                        all_opportunities.extend(opportunities)
                        pbar.update(len(opportunities))
                    if len(all_opportunities) >= target_amount:
                        break
                
                if not cursor:
                    break
                
        return Batch(all_opportunities)

