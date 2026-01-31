import os
import sys
from dotenv import load_dotenv
import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# Ensure we can import from src/ analysis and kalshi packages
# This assumes the file is in src/interface/cli.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.analyzer import Analyzer
from analysis.batch import Batch

class KarbotCLI:
    def __init__(self):
        self.console = Console()
        self.analyzer = None
        self.batch = None
        self.env = "demo" # Default
        self.settings = {
            "target_amount": 5,
            "contract_limit": 1, # Placeholder
        }
        self.keys = {}
        
    def setup(self):
        self.console.clear()
        self.console.print(Panel.fit("[bold cyan]Karbot CLI[/bold cyan]", border_style="cyan"))
        
        # Load .env
        load_dotenv()
        
        # Environment Selection
        self.env = questionary.select(
            "Select Environment:",
            choices=["demo", "prod"]
        ).ask()
        
        if not self.env: # User cancelled
            return False

        # Load keys based on env
        if self.env == "prod":
            self.keys["id"] = os.getenv("KEYID")
            self.keys["file"] = os.getenv("KEYFILE")
        else:
            self.keys["id"] = os.getenv("DEMO_KEYID")
            self.keys["file"] = os.getenv("DEMO_KEYFILE")
            
        if not self.keys["id"] or not self.keys["file"]:
            self.console.print("[bold red]Error:[/bold red] API keys not found for selected environment in .env file.")
            return False
            
        self.console.print(f"[bold green]Initializing Analyzer ({self.env})...")
        # We don't suppress output here as the client might print useful info
        try:
            self.analyzer = Analyzer(self.keys["id"], self.keys["file"], env=self.env)
        except Exception as e:
            self.console.print(f"[bold red]Failed to initialize Analyzer:[/bold red] {e}")
            return False
        
        return True

    def run(self):
        if not self.setup():
            return

        while True:
            self.console.rule()
            choice = questionary.select(
                "Main Menu",
                choices=[
                    "Find Opportunities",
                    "View Current Batch",
                    "Settings",
                    "Exit"
                ]
            ).ask()
            
            if choice == "Find Opportunities":
                self.find_opportunities()
            elif choice == "View Current Batch":
                self.view_batch()
            elif choice == "Settings":
                self.modify_settings()
            elif choice == "Exit":
                self.console.print("Goodbye!")
                break
            elif choice is None: # Handle KeyboardInterrupt/Cancel
                break

    def find_opportunities(self):
        if not self.analyzer:
            self.console.print("[red]Analyzer not initialized.[/red]")
            return

        amount = questionary.text(
            "How many opportunities to find?",
            default=str(self.settings["target_amount"]),
            validate=lambda text: text.isdigit() and int(text) > 0 or "Please enter a positive integer"
        ).ask()
        
        if amount is None: return

        amount = int(amount)
        
        self.console.print(f"Searching for {amount} opportunities...")
        
        try:
            # analyzer.find_opportunities uses tqdm, so it will show a progress bar
            self.batch = self.analyzer.find_opportunities(target_amount=amount)
            self.console.print(f"[bold green]Found {len(self.batch.batch)} opportunities![/bold green]")
            self.view_batch()
        except Exception as e:
            self.console.print(f"[bold red]Error finding opportunities:[/bold red] {e}")

    def view_batch(self):
        if not self.batch or not self.batch.batch:
            self.console.print("[yellow]No batch available. Find opportunities first.[/yellow]")
            return

        table = Table(title=f"Arbitrage Opportunities (Batch of {len(self.batch.batch)})")
        table.add_column("#", justify="right", style="cyan", no_wrap=True)
        table.add_column("Event Ticker", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Type", style="magenta")
        table.add_column("Minimum Profit ($)", justify="right", style="green")
        table.add_column("Cost ($)", justify="right", style="red")
        table.add_column("Markets", justify="right")

        for i, opp in enumerate(self.batch.batch, 1):
            constituents_count = len(opp.constituents)
            table.add_row(
                str(i),
                opp.event_ticker,
                opp.title,
                opp.type,
                f"{opp.profit:.2f}",
                f"{opp.total_cost:.2f}",
                str(constituents_count)
            )
        
        self.console.print(table)
        
        # Option to see details
        if questionary.confirm("View details of a specific opportunity?").ask():
            self.view_opportunity_details()

    def view_opportunity_details(self):
        if not self.batch or not self.batch.batch:
            return
            
        choices = [f"{i+1}. {o.event_ticker} ({o.type})" for i, o in enumerate(self.batch.batch)]
        choices.append("Back")
        
        choice = questionary.select("Select Opportunity:", choices=choices).ask()
        
        if choice == "Back" or not choice:
            return
            
        index = int(choice.split(".")[0]) - 1
        opp = self.batch.batch[index]
        
        self.console.print(Panel(
            f"[bold]Title:[/bold] {opp.title}\n"
            f"[bold]Ticker:[/bold] {opp.event_ticker}\n"
            f"[bold]Type:[/bold] {opp.type.upper()}\n"
            f"[bold]Total Cost:[/bold] ${opp.total_cost:.2f}\n"
            f"[bold]Profit:[/bold] ${opp.profit:.2f}\n",
            title=f"Opportunity {index+1} Details"
        ))
        
        m_table = Table(title="Constituent Markets")
        m_table.add_column("Ticker", style="yellow")
        m_table.add_column("Yes Ask", justify="right")
        m_table.add_column("No Ask", justify="right")
        m_table.add_column("Exp. Date")
        
        for m in opp.constituents:
            m_table.add_row(
                m.ticker,
                str(m.yes_ask),
                str(m.no_ask),
                str(m.exp_date)
            )
        self.console.print(m_table)
        
        questionary.press_any_key_to_continue().ask()

    def modify_settings(self):
        while True:
            choice = questionary.select(
                "Settings",
                choices=[
                    f"Target Amount (Current: {self.settings['target_amount']})",
                    f"Contract Limit (Current: {self.settings['contract_limit']})",
                    "Back"
                ]
            ).ask()
            
            if choice == "Back" or choice is None:
                break
            
            if "Target Amount" in choice:
                 amount = questionary.text(
                    "New target amount:",
                    default=str(self.settings["target_amount"]),
                    validate=lambda text: text.isdigit() and int(text) > 0
                ).ask()
                 if amount:
                    self.settings["target_amount"] = int(amount)
                    
            elif "Contract Limit" in choice:
                 limit = questionary.text(
                    "New contract limit:",
                    default=str(self.settings["contract_limit"]),
                    validate=lambda text: text.isdigit() and int(text) > 0
                ).ask()
                 if limit:
                    self.settings["contract_limit"] = int(limit)

if __name__ == "__main__":
    cli = KarbotCLI()
    cli.run()
