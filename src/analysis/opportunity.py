from .market import Market


class Opportunity:
    """
    Data strucutre to contain opportunity data for an event and some metric methods.
    """
    def __init__(
            self,
            title: str,
            event_ticker: str,
            type: str,
            total_cost: int,
            profit: int,
            constituents: list[Market]
    ):
        self.title = title
        self.event_ticker = event_ticker
        self.type = type
        self.total_cost = total_cost
        self.profit = profit
        self.constituents = constituents

        # TODO
        self.contracts_per = 1


    def print_constituents(self, limit: int=0):
        """
        Prints out all constituents (valid markets) and their data in this event. Will display up to the given limit, or all if no limit is given. Extra markets will be denoted with a '...'
        
        :param limit: Max number of constituents to display. Setting this to a value can avoid messy output for events with many sub markets.
        :type limit: int
        """

        if limit < 0:
            raise ValueError("USER ERROR: Invalid limit paramter. Limit must be >= 0")

        print("Markets:")
        printed = 0 # keep track for limit
        for c in self.constituents:
            if printed == limit and limit != 0:
                print("...")
                break
            c.print_market(self.type)
            printed += 1
        print()

    def print_opportunity(self, verbose: bool=False):
        """
        DPrints out overall summary of this opportunity. e.g. cost/profit.
        
        :param verbose: if True will print out some additional data.
        :type verbose: bool
        """

        print(self.title)
        if verbose:
            print(f"Ticker: {self.event_ticker}")
        print(f"Buy {self.type}.")

        total_cost = self.contracts_per * self.total_cost / 100
        profit = self.contracts_per * self.profit / 100
        print(f"Expected metrics after executing {self.contracts_per} constract(s) per market:")
        print(f"Expected total cost: {total_cost:.2f}")
        print(f"Expected total profit: {profit:.2f}")

        print(f"Found {len(self.constituents)} possible markets optimal for arbitrage.")
        if verbose:
            self.print_constituents()
