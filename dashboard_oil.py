"""
dashboard_oil.py
─────────────────
Live terminal dashboard for monitoring the Brent Crude sentiment bot.
Reads signals_oil.csv and trades_oil.csv — works while bot_oil.py is running.

Run:
  python dashboard_oil.py
  python dashboard_oil.py --refresh 10   # refresh every 10 seconds
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def read_csv_tail(path: str, n: int = 10) -> list[dict]:
    """Read last N rows of a CSV file."""
    try:
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        return rows[-n:]
    except FileNotFoundError:
        return []
    except Exception:
        return []


def color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def score_bar(score: float, width: int = 30) -> str:
    """Render a visual score bar."""
    score = max(-1.0, min(1.0, score))
    mid = width // 2
    pos = int((score + 1) / 2 * width)
    bar = ["-"] * width
    if 0 <= pos < width:
        bar[pos] = "o"
    bar[mid] = bar[mid] if bar[mid] == "o" else "|"
    bar_str = "".join(bar)

    if score > 0.3:
        return color(f"[{bar_str}]", "32")  # green
    elif score < -0.3:
        return color(f"[{bar_str}]", "31")  # red
    else:
        return color(f"[{bar_str}]", "33")  # yellow


def render_dashboard(signal_log: str, trade_log: str):
    signals = read_csv_tail(signal_log, 20)
    trades = read_csv_tail(trade_log, 10)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(color("=" * 65, "34"))
    print(color(f"  BRENT CRUDE (BZ-USD) SENTIMENT BOT DASHBOARD  {now}", "1;34"))
    print(color("=" * 65, "34"))

    # Latest signal
    if signals:
        latest = signals[-1]
        conf = float(latest.get("confidence", 0))
        action = latest.get("action", "?")
        direction = latest.get("contrarian_direction", "?")
        bias = latest.get("news_bias", "?")
        ts = latest.get("timestamp", "?")[:19]

        action_color = "32" if "LONG" in action else "31" if "SHORT" in action else "33"

        print(f"\n  {'LATEST SIGNAL':15}  {ts}")
        print(f"  News bias:  {bias}")
        print(f"  Confidence: {'#' * int(conf * 20):20}  {conf:.0%}")
        print(f"  Direction:  {color(direction, '1')}")
        print(f"  Action:     {color(action, action_color)}")

        reasoning = latest.get("reasoning", "")[:120]
        if reasoning:
            print(f"\n  Reasoning:  {color(reasoning, '2')}")

    # Recent signals table
    print(f"\n  {'-' * 63}")
    print(f"  {'RECENT SIGNALS':}")
    print(color(f"  {'Time':19}  {'Bias':8}  {'Conf':>5}  {'Direction':10}  Action", "2"))
    for sig in reversed(signals[-8:]):
        ts = sig.get("timestamp", "")[:19]
        bias = sig.get("news_bias", "")
        cf = float(sig.get("confidence", 0))
        dr = sig.get("contrarian_direction", "")
        ac = sig.get("action", "")
        bias_colored = color(f"{bias:8}", "32" if bias == "BULLISH" else "31" if bias == "BEARISH" else "33")
        ac_colored = color(f"{ac:12}", "32" if "LONG" in ac else "31" if "SHORT" in ac else "33")
        print(f"  {ts}  {bias_colored}  {cf:5.0%}  {dr:10}  {ac_colored}")

    # Trade history
    print(f"\n  {'-' * 63}")
    print(f"  TRADE HISTORY")
    if trades:
        total_pnl = 0.0
        print(color(f"  {'Time':19}  {'Side':5}  {'Size':9}  {'Price':>10}  {'PnL':>10}  Act", "2"))
        for t in reversed(trades):
            ts = t.get("timestamp", "")[:19]
            side = t.get("side", "")
            size = t.get("size", "")
            price = t.get("price", "")
            pnl = t.get("pnl_usd", "")
            act = t.get("action", "")
            try:
                pnl_val = float(pnl) if pnl else 0
                total_pnl += pnl_val
                pnl_str = color(f"${pnl_val:+.2f}", "32" if pnl_val >= 0 else "31")
            except ValueError:
                pnl_str = "       "
            side_col = color(f"{side:5}", "32" if side == "BUY" else "31")
            try:
                price_str = f"${float(price):>10,.2f}" if price else "          "
            except ValueError:
                price_str = f"{price:>11}"
            print(f"  {ts}  {side_col}  {size:9}  {price_str}  {pnl_str:>10}  {act}")

        print(f"\n  {'Total realized PnL:':35} {color(f'${total_pnl:+.2f}', '32' if total_pnl >= 0 else '31')}")
    else:
        print("  No trades yet.")

    print(color("\n  -" * 32 + "-", "2"))
    print(color("  Press Ctrl+C to exit dashboard", "2"))


def main():
    parser = argparse.ArgumentParser(description="Brent Crude Sentiment Bot Dashboard")
    parser.add_argument("--signal-log", default="signals_oil.csv")
    parser.add_argument("--trade-log", default="trades_oil.csv")
    parser.add_argument("--refresh", type=int, default=15, help="Refresh interval in seconds")
    args = parser.parse_args()

    print("Starting oil dashboard... (waiting for log files)")
    while True:
        try:
            clear()
            render_dashboard(args.signal_log, args.trade_log)
            time.sleep(args.refresh)
        except KeyboardInterrupt:
            print("\nDashboard closed.")
            break


if __name__ == "__main__":
    main()
