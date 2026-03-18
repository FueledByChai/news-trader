# 🤖 BTC Sentiment Trading Bot

Sentiment-driven BTC perpetual futures bot using Claude AI + free news sources + Paradex DEX.

## Architecture

```
Free Data Sources          Claude AI           Paradex DEX
─────────────────    →    ──────────    →     ─────────────
• CryptoPanic API          Sentiment           BTC-USD-PERP
• Google News RSS          Scoring             Order Mgmt
• Reddit API               (-1 to +1)          Position Mon.
• Fear & Greed Index                           Stop/TP
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Free API Keys

| Service | Where | Cost |
|---|---|---|
| **Anthropic** | console.anthropic.com | Pay per use (~$0.001/cycle) |
| **CryptoPanic** | cryptopanic.com/developers/api | Free |
| **Reddit** | reddit.com/prefs/apps | Free (create "script" app) |
| **NewsAPI** | newsapi.org | Free (100 req/day) |

Google News RSS and Fear & Greed Index require **no API key**.

### 3. Configure
Edit `config.yaml`:
```yaml
api_keys:
  anthropic: "sk-ant-..."
  cryptopanic: "abc123..."
  reddit_client_id: "..."
  reddit_client_secret: "..."
```

### 4. Test Pipeline
```bash
python test_pipeline.py
```
This checks all API connections without placing any trades.

### 5. Run in Paper Mode
```bash
python bot.py --dry-run
```

### 6. Monitor with Dashboard
In a second terminal:
```bash
python dashboard.py
```

---

## Configuration Reference (`config.yaml`)

### Trading Parameters
| Key | Default | Description |
|---|---|---|
| `paper_trading` | `true` | Simulate trades (no real orders) |
| `position_size_pct` | `0.05` | 5% of balance per trade |
| `long_threshold` | `0.55` | Score above this → open long |
| `short_threshold` | `-0.55` | Score below this → open short |
| `close_threshold` | `0.15` | Score near zero → close position |
| `stop_loss_pct` | `0.02` | 2% stop loss |
| `take_profit_pct` | `0.04` | 4% take profit |
| `min_confidence` | `0.6` | Min Claude confidence to trade |

### Sentiment Weights
```yaml
weights:
  cryptopanic: 0.30   # Crypto-specific news
  google_news: 0.25   # Broad coverage
  reddit: 0.20        # Community sentiment
  fear_greed: 0.25    # Mechanical contrarian signal
```

### Poll Interval
```yaml
poll_interval_seconds: 300  # Re-score every 5 minutes
```

---

## Going Live (BTC-USD-PERP on Paradex)

When you're ready to trade with real funds:

1. Set `paper_trading: false` in config.yaml
2. Set `network: mainnet`
3. Add your Stark private key (from your Paradex/StarkNet wallet)
4. Add your Paradex account address
5. Install starknet-py: `pip install starknet-py`
6. Follow Paradex auth docs: https://docs.paradex.trade/documentation/getting-started/authentication

> ⚠️ **Start small.** Set `position_size_pct: 0.01` (1%) when first going live.

---

## File Structure
```
btc_sentiment_bot/
├── bot.py              # Main orchestrator & loop
├── news_fetcher.py     # All data source fetchers
├── sentiment_engine.py # Claude scoring logic
├── paradex_trader.py   # Order execution & account mgmt
├── dashboard.py        # Live terminal monitor
├── test_pipeline.py    # Validate setup before running
├── config.yaml         # All settings
├── requirements.txt    # Python dependencies
├── bot.log             # Full run log (auto-created)
├── signals.csv         # Every sentiment signal (auto-created)
└── trades.csv          # Every trade placed (auto-created)
```

---

## Expected Cost per Cycle
- Claude API (claude-sonnet): ~40 headlines × ~100 tokens/headline + scoring ≈ ~$0.001–0.003
- At 5-minute intervals: ~$0.30–0.90/day in Claude API costs
- All news data: **free**

---

## Disclaimer
This bot is for educational purposes. Crypto trading involves significant risk of loss.
Always paper trade first, never risk more than you can afford to lose.
