from .opportunity import Opportunity
from .market import Market


class Batch:
    """
    Data structure to act as a collection of opportunities and perform any necessary operations.
    """
    def __init__(self, batch: list[Opportunity]):
        self.batch = batch
    
    def get_all_markets(self) -> list[Market]:
        """
        Get a list of all individual markets, unrelated to their opportunities.
        
        :return: a list of Market objects.
        :rtype: list[Market]
        """
        result = []
        for o in self.batch:
            result.extend(o.constituents)

    def print_batch(self, verbose: bool=False):
        """
        Print out all opportunities and their data.
        """
        for i, o in enumerate(self.batch):
            print(f"---------------------- Opportunity {i + 1}: {o.event_ticker} ----------------------")
            o.print_opportunity(verbose=verbose)
