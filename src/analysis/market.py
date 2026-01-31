from datetime import datetime


class Market:
    """
    Data structure to contain relevant market information and metric monitoring.

    ticker: market ticker
    yes_ask: price of yes ask in cents
    no_ask: price of no ask in cents
    exp_date: market expiration date
    """
    def __init__(
            self,
            ticker: str,
            yes_ask: int,
            no_ask: int,
            exp_date: str
    ):
        self.ticker = ticker
        self.yes_ask = yes_ask / 100
        self.no_ask = no_ask / 100
        self.exp_date = self._process_date(exp_date)

    def _process_date(self, date: str) -> datetime:
        """
        Private helper to convert ISO 8601 date string to datetime object.
        Kalshi stores dates in their API in the ISO format, so conversion simplifies time comparisons with datetime.
        
        :param date: ISO 8601 formatted date string (e.g., "2023-11-07T05:31:56Z")
        :type date: str
        :return: Parsed datetime object
        :rtype: datetime
        """
        # replace 'Z' with '+00:00' for ISO format compatibility
        if date.endswith('Z'):
            date = date[:-1] + '+00:00'
        return datetime.fromisoformat(date)
    
    def print_market(self, type: str):
        """
        Print market data for user.
        
        :param type: Event bundle type; ('long' or 'short')
        :type type: str
        """
        print(f"Market: {self.ticker}")
        cost = self.yes_ask if type == "long" else self.no_ask
        print(f"Cost of entry per contract: {cost}")
        print(f"Expiration date: {self.exp_date}")
        print()
