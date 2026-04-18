"""
bot.py  —  Session-Based Contrarian Trading Bot
────────────────────────────────────────────────
Strategy:
  At the open of each session (Asia 00:00, London 08:00, NY 13:00 UTC):
    1. Fetch all news published since the previous session open
    2. Ask Claude: what is the general news bias?
    3. Go CONTRARIAN — bullish news → SHORT, bearish news → LONG
    4. Always in the market. Flip at every session open if direction changes.

  On startup:
    Determine the current session, fetch news since that session opened,
    evaluate direction, and enter or flip immediately. Then sleep until
    the next session open.

Run:
  python bot.py               # uses config.yaml
  python bot.py --dry-run     # force paper mode
  python bot.py --once        # evaluate once and exit
  python bot.py --config x.yaml
"""

import argparse
import csv
import logging
import os
import sys
import time
import yaml
import colorlog
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from news_fetcher import fetch_session_news
from sentiment_engine import score_session
from paradex_trader import ParadexTrader

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────────────────────

def setup_logging(cfg: dict):
    level    = getattr(logging, cfg.get("logging", {}).get("level", "INFO").upper(), logging.INFO)
    log_file = cfg.get("logging", {}).get("log_file", "bot.log")

    console = colorlog.StreamHandler()
    console.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s %(levelname)-8s%(reset)s %(message)s",
        datefmt="%H:%M:%S",
        log_colors={"DEBUG":"cyan","INFO":"white","WARNING":"yellow",
                    "ERROR":"red","CRITICAL":"bold_red"},
    ))

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(message)s",
                          datefmt="%Y-%m-%d %H:%M:%S")
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)
    return logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
#  Session schedule (UTC)
# ─────────────────────────────────────────────────────────────

SESSIONS = [
    ("Asia",   0),
    ("London", 8),
    ("NY",     13),
]


def current_session(now: datetime) -> tuple:
    """Returns (session_name, session_open_datetime) for the given UTC time."""
    h = now.hour
    for name, start_hour in reversed(SESSIONS):
        if h >= start_hour:
            open_dt = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            return name, open_dt
    # Before 00:00 UTC — in NY from previous day
    yesterday = now - timedelta(days=1)
    open_dt = yesterday.replace(hour=13, minute=0, second=0, microsecond=0)
    return "NY", open_dt


def next_session_open(now: datetime) -> tuple:
    """Returns (next_session_name, next_session_open_datetime) in UTC."""
    h = now.hour
    for name, start_hour in SESSIONS:
        if h < start_hour:
            open_dt = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            return name, open_dt
    # Past 13:00 — next is Asia tomorrow
    tomorrow = now + timedelta(days=1)
    open_dt = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    return "Asia", open_dt


def seconds_until(target: datetime) -> float:
    return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())


# ─────────────────────────────────────────────────────────────
#  CSV logging
# ─────────────────────────────────────────────────────────────

def log_signal_to_csv(path: str, signal: dict):
    exists = Path(path).exists()
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp","session","news_bias","contrarian_direction",
            "confidence","action","reasoning"
        ])
        if not exists:
            writer.writeheader()
        writer.writerow({
            "timestamp":            signal.get("timestamp",""),
            "session":              signal.get("session",""),
            "news_bias":            signal.get("news_bias",""),
            "contrarian_direction": signal.get("contrarian_direction",""),
            "confidence":           round(signal.get("confidence",0) or 0, 3),
            "action":               signal.get("action",""),
            "reasoning":            signal.get("reasoning","")[:300],
        })


def log_trade_to_csv(path: str, trade: dict):
    exists = Path(path).exists()
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp","market","side","size","price",
            "notional_usd","paper","action","pnl_usd"
        ])
        if not exists:
            writer.writeheader()
        writer.writerow({
            "timestamp":    trade.get("close_timestamp", trade.get("timestamp","")),
            "market":       trade.get("market",""),
            "side":         trade.get("side",""),
            "size":         trade.get("size",""),
            "price":        trade.get("close_price", trade.get("entry_price","")),
            "notional_usd": round(trade.get("notional_usd",0),2),
            "paper":        trade.get("paper",True),
            "action":       trade.get("action",""),
            "pnl_usd":      round(trade.get("pnl_usd",0) or 0,2),
        })


# ─────────────────────────────────────────────────────────────
#  Core evaluation
# ─────────────────────────────────────────────────────────────

def evaluate_and_trade(trader: ParadexTrader, cfg: dict,
                       session_name: str, session_open: datetime,
                       force_label: str = "") -> dict:
    """
    Fetch news since session_open, score with Claude, determine contrarian
    direction, and open/flip/hold accordingly.
    """
    label   = force_label or session_name
    now_utc = datetime.now(timezone.utc)

    log.info("━" * 60)
    log.info(f"  {label} evaluation  "
             f"(session opened: {session_open.strftime('%Y-%m-%d %H:%M UTC')})")
    log.info("━" * 60)

    hours_back = max(1.0, (now_utc - session_open).total_seconds() / 3600)
    log.info(f"  Fetching news from last {hours_back:.1f}h")

    # 1. Fetch news for this session window
    raw = fetch_session_news(cfg, hours_back=hours_back)

    # 2. Score with Claude
    result = score_session(raw, cfg, session_name=label)

    news_bias      = result.get("news_bias", "NEUTRAL")
    contrarian_dir = result.get("contrarian_direction", "LONG")
    confidence     = result.get("confidence", 0.5)

    log.info(f"  News bias: {news_bias}  →  Contrarian: {contrarian_dir}  "
             f"(confidence={confidence:.2f})")
    log.info(f"  Reasoning: {result.get('reasoning','')}")

    # 3. Determine action vs current position
    position     = trader.get_open_position()
    current_side = None
    if position:
        current_side = "LONG" if position.get("side") == "BUY" else "SHORT"

    action    = "HOLD"
    trade_res = None

    if contrarian_dir == "LONG":
        if current_side == "LONG":
            action = "HOLD"
            log.info("  Already LONG — holding")
        elif current_side == "SHORT":
            action = "FLIP_TO_LONG"
            log.info("  Flipping SHORT → LONG")
            closed = trader.close_position()
            if closed:
                log_trade_to_csv(cfg["logging"]["trade_log"],
                                 {**closed, "action": "FLIP_CLOSE"})
            trade_res = trader.open_long(open_reason=f"{label}_session")
        else:
            action = "OPEN_LONG"
            log.info("  No position — opening LONG")
            trade_res = trader.open_long(open_reason=f"{label}_session")

    elif contrarian_dir == "SHORT":
        if current_side == "SHORT":
            action = "HOLD"
            log.info("  Already SHORT — holding")
        elif current_side == "LONG":
            action = "FLIP_TO_SHORT"
            log.info("  Flipping LONG → SHORT")
            closed = trader.close_position()
            if closed:
                log_trade_to_csv(cfg["logging"]["trade_log"],
                                 {**closed, "action": "FLIP_CLOSE"})
            trade_res = trader.open_short(open_reason=f"{label}_session")
        else:
            action = "OPEN_SHORT"
            log.info("  No position — opening SHORT")
            trade_res = trader.open_short(open_reason=f"{label}_session")

    else:
        # NEUTRAL — keep current, default to LONG if nothing open
        if current_side:
            action = "HOLD"
            log.info(f"  Neutral news — holding existing {current_side}")
        else:
            action = "OPEN_LONG"
            log.info("  Neutral news, no position — defaulting to LONG")
            trade_res = trader.open_long(open_reason=f"{label}_session")

    if trade_res:
        log_trade_to_csv(cfg["logging"]["trade_log"], {**trade_res, "action": action})

    # 4. Status
    status  = trader.status_report()
    price   = status.get("mark_price", 0)
    balance = status.get("balance_usd", 0)
    upnl    = status.get("unrealized_pnl", 0)
    rpnl    = status.get("realized_pnl", 0)

    log.info(f"  STATUS  BTC=${price:,.2f}  balance=${balance:,.2f}  "
             f"unrealized=${upnl:+.2f}  realized=${rpnl:+.2f}")

    signal = {
        "timestamp":            now_utc.isoformat(),
        "session":              label,
        "news_bias":            news_bias,
        "contrarian_direction": contrarian_dir,
        "confidence":           confidence,
        "action":               action,
        "reasoning":            result.get("reasoning",""),
    }
    log_signal_to_csv(cfg["logging"]["signal_log"], signal)
    return signal


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Session-Based Contrarian Bot")
    parser.add_argument("--config",  default="config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once",    action="store_true",
                        help="Evaluate current session and exit")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)

    load_dotenv()

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    if args.dry_run:
        cfg["trading"]["paper_trading"] = True

    global log
    log = setup_logging(cfg)

    env_key = os.getenv("ANTHROPIC_API_KEY")
    if env_key:
        cfg["api_keys"]["anthropic"] = env_key

    if cfg["api_keys"]["anthropic"].startswith("YOUR_"):
        log.error("Set your Anthropic API key in config.yaml or .env")
        sys.exit(1)

    paper = cfg["trading"]["paper_trading"]
    log.info("🤖 Session-Based Contrarian Bot")
    log.info(f"   Market: {cfg['paradex']['market']}")
    log.info(f"   Mode:   {'PAPER' if paper else '⚠️  LIVE'}")
    log.info(f"   Sessions: Asia 00:00 | London 08:00 | NY 13:00 (all UTC)")
    log.info(f"   Always in market — bullish news → SHORT, bearish → LONG")

    trader = ParadexTrader(cfg)

    # Startup: evaluate current session immediately
    now_utc = datetime.now(timezone.utc)
    sess_name, sess_open = current_session(now_utc)
    log.info(f"  Currently in {sess_name} session "
             f"(opened {sess_open.strftime('%H:%M UTC')})")

    evaluate_and_trade(trader, cfg, sess_name, sess_open,
                       force_label=f"STARTUP/{sess_name}")

    if args.once:
        return

    # Main loop: sleep to next session open, evaluate, repeat
    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            next_name, next_open = next_session_open(now_utc)
            secs = seconds_until(next_open)

            log.info(f"  Next: {next_name} opens at "
                     f"{next_open.strftime('%Y-%m-%d %H:%M UTC')} "
                     f"(in {secs/3600:.1f}h / {secs/60:.0f}min)")
            time.sleep(secs + 2)

            now_utc = datetime.now(timezone.utc)
            fire_name, fire_open = current_session(now_utc)
            evaluate_and_trade(trader, cfg, fire_name, fire_open)

        except KeyboardInterrupt:
            log.info("\nBot stopped.")
            status = trader.status_report()
            if status.get("realized_pnl") is not None:
                log.info(f"Final realized PnL: ${status['realized_pnl']:+.2f}")
            break
        except Exception as e:
            log.error(f"Unexpected error: {e}", exc_info=True)
            log.info("Will retry at next session open in 60s...")
            time.sleep(60)


if __name__ == "__main__":
    main()