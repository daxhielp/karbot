# Karbot - Kalshi Arbitrage Bot

**K**alshi **Ar**bitrage **Bot** is a Python-based arbitrage bot for finding and analyzing risk-free profit opportunities on the Kalshi prediction market platform.

## Overview

Karbot is an automated tool that scans Kalshi events to identify arbitrage opportunities in mutually exclusive prediction markets. By analyzing market prices across multiple outcomes, it finds situations where buying certain combinations of contracts guarantees a profit regardless of the outcome.

## What is Arbitrage?

Arbitrage is a trading strategy that exploits price inefficiencies to guarantee a profit with zero risk. In prediction markets with mutually exclusive outcomes (where exactly one outcome must occur), arbitrage opportunities arise when:

1. **Bundle Long Arbitrage**: The sum of "Yes" prices across all outcomes is less than 100¢ (the guaranteed payout when one outcome occurs)
2. **Bundle Short Arbitrage**: The sum of "No" prices across all outcomes is less than (N-1) × 100¢ (the payout when N-1 outcomes lose)

### Example

Consider an election with 3 candidates (A, B, C):

- Candidate A "Yes": 30¢
- Candidate B "Yes": 35¢
- Candidate C "Yes": 25¢

**Total cost**: 90¢  
**Guaranteed payout**: 100¢ (one candidate must win)  
**Risk-free profit**: 10¢ per bundle

## Core Functionality

### Architecture

The bot is organized into three main components:

1. **KalshiClient** (`src/kalshi/kalshi_client.py`):
   - Handles API authentication using RSA signatures
   - Provides methods for querying events, markets, and account balance
   - Manages rate limiting and request signing

2. **Analyzer** (`src/analyzer.py`):
   - Extends KalshiClient with arbitrage detection logic
   - Filters valid markets based on status and price bounds
   - Identifies bundle long and bundle short opportunities
   - Handles pagination to search through large numbers of events

3. **Data Models**:
   - **Market**: Stores individual market data (ticker, prices, expiration)
   - **Opportunity**: Represents a detected arbitrage opportunity with constituent markets

### Arbitrage Detection Algorithm

```python
# Bundle Long: Sum of Yes asks < 100
if sum(yes_asks) < 100:
    profit = 100 - sum(yes_asks)
    # Create long opportunity

# Bundle Short: Sum of No asks < (N-1) × 100
if sum(no_asks) < (len(markets) - 1) * 100:
    profit = (len(markets) - 1) * 100 - sum(no_asks)
    # Create short opportunity
```

The bot validates each market by checking:

- Market status is "active"
- Ask prices are within valid bounds (0 < price < 100)
- Event has mutually exclusive outcomes

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- Kalshi API account (demo or production)
- Kalshi API key ID and RSA private key file

### Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/daxhielp/karbot
   cd karbot
   ```

2. **(Optional) Create virtual environment**

   ```bash
   python -m venv env_name
   env_name/Scripts/Activate.ps1
   ```

3. **Install dependencies**:

   ```bash
   cd src
   pip install -r requirements.txt
   ```

4. **Set up API credentials**:

   Create a `.env` file in the `src` directory:

   ```env
   # Demo environment
   DEMO_KEYID=your_demo_key_id
   DEMO_KEYFILE=/path/to/demo_private_key.pem

   # Production environment
   KEYID=your_prod_key_id
   KEYFILE=/path/to/prod_private_key.pem
   ```

   You can also read the (`.env.example`) file for reference

5. **Store your RSA private keys**:
   - We suggest storing your Kalshi RSA private key files in a new directory like `src/keys/`
   - Update the `.env` file with the correct paths
   - Ensure the files are in PEM format

### Obtaining Kalshi API Keys

1. Sign up at [Kalshi](https://kalshi.com) or [Kalshi Demo](https://demo.kalshi.co)
2. Navigate to API settings in your account
3. Generate an API key pair (Key ID + RSA private key)
4. Download the private key file (.pem)
5. Copy the Key ID to your `.env` file

## Usage

### Running the Bot

```bash
cd src
python main.py
```

### Configuration

Edit `main.py` to configure:

```python
ENV = "demo"  # or "prod" for production

# Find N arbitrage opportunities
prospects = client.find_opportunities(target_amount=10)
```

### Output

The bot displays:

- Current account balance
- Detected opportunities with event titles and tickers
- Expected cost and profit for each opportunity
- Constituent markets with pricing details

Example output:

```
Balance: $10000.00

---------------------- Opportunity 1: ELECTION-2026 ----------------------
Presidential Election Winner
Expected total cost for at-price bid: $0.92
Expected profit for at-price bid: $0.08

Markets:
Market: ELECTION-CANDIDATE-A
Cost of entry per contract: 30
Expiration date: 2026-11-03 20:00:00+00:00
```

## Project Structure

```
karbot/
├── src/
│   ├── main.py              # Entry point
│   ├── analyzer.py          # Core arbitrage logic
│   ├── requirements.txt     # Python dependencies
│   ├── kalshi/
│   │   └── kalshi_client.py # Kalshi API wrapper
│   └── keys/
│       ├── demo.txt         # Demo key storage
│       └── prod.txt         # Production key storage
└── README.md
```

## Rate Limiting

The bot automatically respects Kalshi API rate limits:

- Reads your account's rate limit on initialization
- Sleeps between requests: `1.1 / read_limit` seconds
- Default: 1 second between requests if limit unknown

## Limitations & Considerations

- **Market Efficiency**: Arbitrage opportunities are rare as markets are generally efficient
- **Execution Risk**: Prices may change between detection and order placement
- **API Costs**: Frequent polling may consume API rate limits
- **Capital Requirements**: Executing arbitrage requires sufficient account balance
- **Demo vs Production**: Always test with demo environment before using real funds

## Future Enhancements

- [ ] Automated order placement
- [ ] Real-time WebSocket monitoring
- [ ] Portfolio tracking and P&L reporting
- [ ] Advanced filtering (minimum profit threshold, expiration date)
- [ ] Support for non-mutually-exclusive arbitrage patterns

## Disclaimer

This project is for educational purposes. Always comply with Kalshi's Terms of Service. Prediction market trading involves risk. The authors are not responsible for any financial losses incurred through the use of this software.

This is NOT financial advice.
