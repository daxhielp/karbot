import os
import sys
from dotenv import load_dotenv
import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

# Ensure we can import from src/ analysis and kalshi packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.analyzer import Analyzer
from analysis.batch import Batch
from analysis.opportunity import Opportunity
from execution.executor import Executor
from config.config_loader import load_execution_config, save_execution_config

class KarbotCLI:
    def __init__(self):
        self.console = Console()
        self.analyzer = None
        self.batch = None
        self.executor = None
        self.env = "demo" # Default
        self.config = {}
        self.keys = {}
        
    def setup(self):
        self.console.clear()
        banner = r"""
$$\   $$\                    $$\                  $$\     
$$ | $$  |                   $$ |                 $$ |    
$$ |$$  / $$$$$$\   $$$$$$\  $$$$$$$\   $$$$$$\ $$$$$$\   
$$$$$  /  \____$$\ $$  __$$\ $$  __$$\ $$  __$$\\_$$  _|  
$$  $$<   $$$$$$$ |$$ |  \__|$$ |  $$ |$$ /  $$ | $$ |    
$$ |\$$\ $$  __$$ |$$ |      $$ |  $$ |$$ |  $$ | $$ |$$\ 
$$ | \$$\\$$$$$$$ |$$ |      $$$$$$$  |\$$$$$$  | \$$$$  |
\__|  \__|\_______|\__|      \_______/  \______/   \____/
"""
        self.console.print(f"[bold cyan]{banner}[/bold cyan]")
        
        # Load .env
        load_dotenv()
        
        # Load config
        try:
            self.config = load_execution_config()
        except Exception as e:
            self.console.print(f"[bold red]Failed to load config:[/bold red] {e}")
            # Initialize with basic structure if failed
            self.config = {
                "execution": {
                    "dry_run": True,
                    "paper_trading": False,
                    "thresholds": {"min_profit_cents": 5, "max_position_size_cents": 10000},
                    "timing": {"execution_timeout_seconds": 60, "poll_interval_seconds": 2},
                    "validation": {"refresh_prices": True}
                },
                "cli": {
                    "target_amount": 5,
                    "contract_limit": 1
                }
            }
        
        # Ensure cli section exists
        if "cli" not in self.config:
            self.config["cli"] = {"target_amount": 5, "contract_limit": 1}

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
        try:
            self.analyzer = Analyzer(self.keys["id"], self.keys["file"], env=self.env)
        except Exception as e:
            self.console.print(f"[bold red]Failed to initialize Analyzer:[/bold red] {e}")
            return False

        # Initialize Executor
        try:
            self.executor = Executor(self.analyzer, self.config)
            mode_str = "Paper Trading" if self.executor.paper_trading else ("Dry Run" if self.executor.dry_run else "Live Execution")
            self.console.print(f"[bold green]Executor initialized ({mode_str})[/bold green]")
        except Exception as e:
            self.console.print(f"[bold red]Failed to initialize Executor:[/bold red] {e}")
        
        return True

    def run(self):
        if not self.setup():
            return

        while True:
            self.console.rule()
            choices = ["Find Opportunities", "View Current Batch"]
            if self.batch and self.batch.batch:
                choices.append("Execute Opportunities")
            choices.extend(["Manage Positions", "Settings", "Exit"])
            
            choice = questionary.select(
                "Main Menu",
                choices=choices
            ).ask()
            
            if choice == "Find Opportunities":
                self.find_opportunities()
            elif choice == "Execute Opportunities":
                self.execute_opportunities()
            elif choice == "View Current Batch":
                self.view_batch()
            elif choice == "Manage Positions":
                self.manage_positions()
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
            default=str(self.config["cli"].get("target_amount", 5)),
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

    def manage_positions(self):
        if not self.executor:
            self.console.print("[red]Executor not initialized.[/red]")
            return

        with self.console.status("Fetching positions...") as status:
            try:
                data = self.executor.client.get_positions()
                market_positions = data.get("market_positions", [])
                
                # Filter for active positions
                active_positions = [m for m in market_positions if m.get("position", 0) != 0]
                
            except Exception as e:
                self.console.print(f"[bold red]Error fetching positions:[/bold red] {e}")
                return

        if not active_positions:
            self.console.print("[yellow]No active market positions found.[/yellow]")
            return

        # --- Display All Positions ---
        table = Table(title="Current Market Positions")
        table.add_column("#", style="cyan")
        table.add_column("Market Ticker", style="white")
        table.add_column("Positions", justify="right")
        table.add_column("PnL ($)", justify="right", style="green")

        for i, pos in enumerate(active_positions, 1):
            table.add_row(
                str(i),
                pos.get("ticker", "N/A"),
                str(abs(pos.get("position", 0))),             # Kalshi positions are negative if they are NO contracts
                pos.get("realized_pnl_dollars", "0.00")
            )

        self.console.print(table)

        choices = [f"{i+1}. {p.get('ticker')}" for i, p in enumerate(active_positions)]
        choices.append("Back")

        choice = questionary.select("Select Position:", choices=choices).ask()

        if choice == "Back" or not choice:
            return

        index = int(choice.split(".")[0]) - 1
        pos = active_positions[index]
        ticker = pos.get("ticker")

        while True:
            action = questionary.select(
                f"Action for {ticker}:",
                choices=["Sell", "View Market Details", "Back"]
            ).ask()

            if action == "Back" or not action:
                return

            if action == "View Market Details":
                with self.console.status(f"Fetching details for {ticker}...") as status:
                    try:
                        m = self.executor.client.get_market(ticker).get("market")
                    except Exception as e:
                        self.console.print(f"[red]Error fetching market details: {e}[/red]")
                # Display details
                self.console.print(Panel(
                    f"[bold]Ticker:[/bold] {m.get('ticker')}\n"
                    f"[bold]Status:[/bold] {m.get('status')}\n"
                    f"[bold]Yes Bid/Ask:[/bold] {m.get('yes_bid', 0)} / {m.get('yes_ask', 0)}\n"
                    f"[bold]No Bid/Ask:[/bold] {m.get('no_bid', 0)} / {m.get('no_ask', 0)}\n"
                    f"[bold]Last Price:[/bold] {m.get('last_price', 'N/A')}\n"
                    f"[bold]Volume:[/bold] {m.get('volume', 0)}\n"
                    f"[bold]Expiration:[/bold] {m.get('expiration_time')}",
                    title="Market Details"
                ))
                questionary.press_any_key_to_continue().ask()
                continue

            elif action == "Sell":
                max_qty = abs(pos.get("position", 0))
                qty = questionary.text(f"Quantity to sell (Max {max_qty}):", default=str(max_qty), 
                                       validate=lambda x: x.isdigit() and 0 < int(x) <= max_qty).ask()
                
                if not qty: return
                qty = int(qty)

                if not questionary.confirm(f"Sell {qty} contracts of {ticker}?").ask():
                    return

                try:
                    orders = self.executor.create_orders_from_positions([pos], quantity=qty)
                    with self.console.status("Submitting sell orders...") as status:
                        res = self.executor.execute_orders(orders)
                    
                    self.console.print(f"Submitted {res['successful_submissions']} orders.")
                    
                    if res['successful_submissions'] > 0:
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            BarColumn(),
                            TextColumn("{task.percentage:>3.0f}%"),
                            transient=False 
                        ) as progress:
                            task = progress.add_task("[cyan]Monitoring fills...", total=len(orders))
                            def progress_cb(filled, pending):
                                progress.update(task, completed=len(filled))
                            self.executor.monitor_orders(orders, progress_callback=progress_cb)
                        
                        self.display_execution_results(orders, None)
                except Exception as e:
                    self.console.print(f"[bold red]Error executing sell:[/bold red] {e}")
                
                # Exit loop after sell attempt
                break

    def modify_settings(self):
        while True:
            choice = questionary.select(
                "Settings",
                choices=[
                    "CLI Settings (Target Amount, etc.)",
                    "Execution Mode (Dry Run, Paper Trading)",
                    "Thresholds (Profit, Position Size)",
                    "Timing (Timeouts, Polling)",
                    "Validation (Price Refresh, Deviation)",
                    "Save & Back",
                    "Cancel"
                ]
            ).ask()
            
            if choice == "Cancel" or choice is None:
                # Reload config to discard changes if cancelled
                try:
                    self.config = load_execution_config()
                except:
                    pass
                break
            
            if choice == "Save & Back":
                try:
                    save_execution_config(self.config)
                    # Re-initialize executor with new config
                    if self.analyzer:
                        self.executor = Executor(self.analyzer, self.config)
                    self.console.print("[bold green]Settings saved and applied.[/bold green]")
                except Exception as e:
                    self.console.print(f"[bold red]Failed to save settings:[/bold red] {e}")
                break

            exec_cfg = self.config.get("execution", {})
            cli_cfg = self.config.get("cli", {})

            if choice == "CLI Settings (Target Amount, etc.)":
                cli_cfg["target_amount"] = int(questionary.text(
                    "Target Amount (Opportunities to find):",
                    default=str(cli_cfg.get("target_amount", 5)),
                    validate=lambda x: x.isdigit() and int(x) > 0
                ).ask() or cli_cfg.get("target_amount", 5))
                
                cli_cfg["contract_limit"] = int(questionary.text(
                    "Contract Limit (Placeholder):",
                    default=str(cli_cfg.get("contract_limit", 1)),
                    validate=lambda x: x.isdigit() and int(x) > 0
                ).ask() or cli_cfg.get("contract_limit", 1))

            elif choice == "Execution Mode (Dry Run, Paper Trading)":
                exec_cfg["dry_run"] = questionary.confirm(
                    "Dry Run (Simulate execution without real orders)?",
                    default=exec_cfg.get("dry_run", True)
                ).ask()
                
                exec_cfg["paper_trading"] = questionary.confirm(
                    "Paper Trading (Simulate fills based on market prices)?",
                    default=exec_cfg.get("paper_trading", False)
                ).ask()

            elif choice == "Thresholds (Profit, Position Size)":
                thresholds = exec_cfg.setdefault("thresholds", {})
                
                thresholds["min_profit_cents"] = int(questionary.text(
                    "Minimum Profit (Cents):",
                    default=str(thresholds.get("min_profit_cents", 5)),
                    validate=lambda x: x.isdigit()
                ).ask() or thresholds.get("min_profit_cents", 5))

                thresholds["max_position_size_cents"] = int(questionary.text(
                    "Max Position Size (Cents):",
                    default=str(thresholds.get("max_position_size_cents", 10000)),
                    validate=lambda x: x.isdigit()
                ).ask() or thresholds.get("max_position_size_cents", 10000))

                thresholds["min_time_to_expiry_hours"] = int(questionary.text(
                    "Min Time to Expiry (Hours):",
                    default=str(thresholds.get("min_time_to_expiry_hours", 24)),
                    validate=lambda x: x.isdigit()
                ).ask() or thresholds.get("min_time_to_expiry_hours", 24))

            elif choice == "Timing (Timeouts, Polling)":
                timing = exec_cfg.setdefault("timing", {})
                
                timing["execution_timeout_seconds"] = int(questionary.text(
                    "Execution Timeout (Seconds):",
                    default=str(timing.get("execution_timeout_seconds", 60)),
                    validate=lambda x: x.isdigit()
                ).ask() or timing.get("execution_timeout_seconds", 60))

                timing["poll_interval_seconds"] = int(questionary.text(
                    "Poll Interval (Seconds):",
                    default=str(timing.get("poll_interval_seconds", 2)),
                    validate=lambda x: x.isdigit()
                ).ask() or timing.get("poll_interval_seconds", 2))

            elif choice == "Validation (Price Refresh, Deviation)":
                validation = exec_cfg.setdefault("validation", {})
                
                validation["refresh_prices"] = questionary.confirm(
                    "Refresh Prices before execution?",
                    default=validation.get("refresh_prices", True)
                ).ask()

                validation["max_price_deviation_percent"] = int(questionary.text(
                    "Max Price Deviation (%) before cancel:",
                    default=str(validation.get("max_price_deviation_percent", 5)),
                    validate=lambda x: x.isdigit()
                ).ask() or validation.get("max_price_deviation_percent", 5))

    def execute_opportunities(self):
        if not self.executor:
            self.console.print("[red]Executor not initialized.[/red]")
            return

        if not self.batch or not self.batch.batch:
            self.console.print("[yellow]No batch available.[/yellow]")
            return

        # Show batch first
        self.view_batch()
        
        # Select opportunity
        choices = [f"{i+1}. {o.event_ticker} ({o.type}) - Profit: ${o.profit:.2f}" for i, o in enumerate(self.batch.batch)]
        choices.append("Back")
        
        choice = questionary.select("Select Opportunity to Execute:", choices=choices).ask()
        
        if choice == "Back" or not choice:
            return
            
        index = int(choice.split(".")[0]) - 1
        opp = self.batch.batch[index]
        
        # Details
        self.console.print(Panel(
            f"[bold]Event:[/bold] {opp.event_ticker}\n"
            f"[bold]Type:[/bold] {opp.type}\n"
            f"[bold]Expected Cost per Set:[/bold] ${opp.total_cost:.2f}\n"
            f"[bold]Expected Profit per Set:[/bold] ${opp.profit:.2f}\n"
            f"[bold]Markets:[/bold] {len(opp.constituents)}",
            title="Opportunity Details"
        ))
        
        if not questionary.confirm("Execute this opportunity?").ask():
            return
            
        qty = questionary.text("How many contracts per market?", default="1", validate=lambda x: x.isdigit() and int(x) > 0).ask()
        if not qty: return
        qty = int(qty)
        
        # Validation
        with self.console.status("Validating execution...") as status:
            valid, msg = self.executor.validate_execution(opp, qty)
            
        if not valid:
            self.console.print(f"[bold red]Validation Failed:[/bold red] {msg}")
            return
            
        # Final Confirm
        total_cost = opp.total_cost * qty
        total_profit = opp.profit * qty
        self.console.print(f"[bold yellow]Execute {qty} contracts?[/bold yellow] Est. Cost: ~${total_cost:.2f}, Est. Profit: ~${total_profit:.2f}")
        if not questionary.confirm("Confirm Execution").ask():
            return
            
        # Execute
        try:
            # Create orders
            orders = self.executor.create_orders_from_opportunity(opp, qty, refresh_prices=True)
            
            # Submit
            with self.console.status("Submitting orders...") as status:
                res = self.executor.execute_orders(orders)
            
            self.console.print(f"Submitted {res['successful_submissions']} orders.")
            
            # Monitor
            if res['successful_submissions'] > 0:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("{task.percentage:>3.0f}%"),
                    transient=False 
                ) as progress:
                    task = progress.add_task("[cyan]Monitoring fills...", total=len(orders))
                    
                    def progress_cb(filled, pending):
                        # Update progress to match filled count
                        progress.update(task, completed=len(filled))
                        
                    monitor_res = self.executor.monitor_orders(orders, progress_callback=progress_cb)
                
                # Pass orders list to display function as it has the final status
                self.display_execution_results(orders, opp)
            else:
                self.console.print("[bold red]No orders were successfully submitted.[/bold red]")
                
        except Exception as e:
            self.console.print(f"[bold red]Execution Error:[/bold red] {e}")

    def display_execution_results(self, orders: list, opportunity: Opportunity):
        table = Table(title="Execution Results")
        table.add_column("Ticker", style="cyan")
        table.add_column("Side", style="magenta")
        table.add_column("Qty", justify="right")
        table.add_column("Price", justify="right")
        table.add_column("Order ID", style="dim")
        table.add_column("Status", style="bold")
        
        total_cost = 0.0
        filled_count = 0
        
        for order in orders:
            status_style = "green" if order.status in ["filled", "executed"] else "yellow" if order.status in ["submitted", "pending"] else "red"
            table.add_row(
                order.ticker,
                order.side,
                str(order.count),
                f"${order.price:.2f}",
                str(order.order_id),
                f"[{status_style}]{order.status.upper()}[/{status_style}]"
            )
            if order.status in ["filled", "executed"]:
                total_cost += order.price * order.count
                filled_count += 1
                
        self.console.print(table)
        
        status_text = "SUCCESS" if filled_count == len(orders) else "PARTIAL" if filled_count > 0 else "FAILED"
        status_color = "green" if status_text == "SUCCESS" else "yellow" if status_text == "PARTIAL" else "red"
        
        summary = f"[bold]Total Actual Cost:[/bold] ${total_cost:.2f} | [bold]Status:[/bold] [{status_color}]{status_text}[/{status_color}]"
        
        if self.executor.logger:
             summary += f"\nExecution logged to: {self.executor.logger.log_file}"
             
        self.console.print(Panel(summary, title="Execution Summary"))

if __name__ == "__main__":
    cli = KarbotCLI()
    cli.run()