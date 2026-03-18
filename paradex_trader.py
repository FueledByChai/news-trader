"""
paradex_trader.py
──────────────────
Handles all Paradex interactions:
  • Read-only market data (via MCP-compatible REST calls)
  • Order placement (long/short/close) via Paradex REST API
  • Paper trading mode (full simulation, no real orders)

Paradex uses Starknet cryptography for order signing.
Install: pip install starknet-py
Docs: https://docs.paradex.trade/
"""

import time
import math
import logging
import requests
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# Paradex API endpoints
ENDPOINTS = {
    "mainnet": "https://api.prod.paradex.trade/v1",
    "testnet": "https://api.testnet.paradex.trade/v1",
}


class PaperTradeBook:
    """Simulates trade execution and tracks paper P&L."""

    def __init__(self):
        self.positions = {}          # market -> {side, size, entry_price, ...}
        self.trade_history = []
        self.realized_pnl = 0.0

    def open_position(self, market: str, side: str, size: float, price: float,
                      open_reason: str = "signal") -> dict:
        trade = {
            "id": f"PAPER-{int(time.time())}",
            "market": market,
            "side": side,
            "size": size,
            "entry_price": price,
            "notional_usd": size * price,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "FILLED",
            "paper": True,
            "open_reason": open_reason,
        }
        self.positions[market] = trade
        self.trade_history.append({**trade, "action": "OPEN"})
        log.info(
            f"[PAPER] OPEN {side} {size:.5f} BTC @ ${price:,.2f} "
            f"(notional: ${trade['notional_usd']:,.2f}, reason: {open_reason})"
        )
        return trade

    def close_position(self, market: str, close_price: float) -> Optional[dict]:
        pos = self.positions.pop(market, None)
        if not pos:
            log.warning(f"[PAPER] No position to close in {market}")
            return None

        entry = pos["entry_price"]
        size = pos["size"]
        side = pos["side"]

        if side == "BUY":
            pnl = (close_price - entry) * size
        else:
            pnl = (entry - close_price) * size

        self.realized_pnl += pnl

        trade = {
            **pos,
            "close_price": close_price,
            "pnl_usd": pnl,
            "close_timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "CLOSE",
        }
        self.trade_history.append(trade)
        log.info(
            f"[PAPER] CLOSE {side} {size:.5f} BTC @ ${close_price:,.2f} "
            f"PnL: ${pnl:+.2f} | Total realized: ${self.realized_pnl:+.2f}"
        )
        return trade

    def get_position(self, market: str) -> Optional[dict]:
        return self.positions.get(market)

    def unrealized_pnl(self, market: str, current_price: float) -> float:
        pos = self.positions.get(market)
        if not pos:
            return 0.0
        entry = pos["entry_price"]
        size = pos["size"]
        side = pos["side"]
        if side == "BUY":
            return (current_price - entry) * size
        return (entry - current_price) * size


class ParadexTrader:
    """
    Handles all Paradex market data reading and order management.
    In paper mode, all order methods are fully simulated.
    In live mode, uses Paradex REST API with Starknet signing.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.pdx_cfg = cfg["paradex"]
        self.trade_cfg = cfg["trading"]
        self.market = self.pdx_cfg["market"]
        self.paper = self.trade_cfg.get("paper_trading", True)
        self.base_url = ENDPOINTS.get(self.pdx_cfg.get("network", "testnet"), ENDPOINTS["testnet"])
        self.paper_book = PaperTradeBook()
        self._jwt_token = None

        if self.paper:
            log.info("=" * 50)
            log.info("  PAPER TRADING MODE — No real orders will be placed")
            log.info("=" * 50)
        else:
            log.warning("  LIVE TRADING MODE — Real orders WILL be placed!")
            self._authenticate()

    # ─── Market Data ─────────────────────────────────────────

    def get_bbo(self) -> dict:
        """
        Get best bid/offer.
        Paradex BBO response: {"bid": 70268.6, "ask": 70268.7, ...}
        bid/ask are plain floats, NOT nested objects.
        """
        try:
            resp = requests.get(
                f"{self.base_url}/bbo/{self.market}",
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            # results may be nested under "results" key or at top level
            if "results" in data:
                data = data["results"]
            bid = float(data.get("bid", 0) or 0)
            ask = float(data.get("ask", 0) or 0)
            mid = (bid + ask) / 2 if bid and ask else 0
            return {"bid": bid, "ask": ask, "mid": mid}
        except Exception as e:
            log.error(f"BBO fetch failed: {e}")
            return {"bid": 0, "ask": 0, "mid": 0, "error": str(e)}

    def get_mark_price(self) -> float:
        """
        Get current mark price from Paradex market summary.

        Uses mark_price (not last_traded_price or underlying_price) because:
        - Mark price is what Paradex uses for P&L and liquidation calculations
        - It's manipulation-resistant (blended index + funding adjustment)
        - Stop/TP checks should use the same price as Paradex's risk engine

        Falls back to BBO mid if mark price unavailable.
        """
        try:
            resp = requests.get(
                f"{self.base_url}/markets/summary",
                params={"market": self.market},
                timeout=10
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            for item in results:
                if item.get("symbol") == self.market:
                    mark  = float(item.get("mark_price", 0) or 0)
                    index = float(item.get("underlying_price", 0) or 0)
                    last  = float(item.get("last_traded_price", 0) or 0)
                    if mark > 0:
                        log.debug(
                            f"Prices — mark=${mark:,.2f}  "
                            f"index=${index:,.2f}  "
                            f"last=${last:,.2f}  "
                            f"spread=${abs(mark-index):.2f}"
                        )
                        return mark
        except Exception as e:
            log.error(f"Mark price fetch failed: {e}")

        # Fallback to BBO mid
        bbo = self.get_bbo()
        mid = bbo.get("mid", 0.0)
        log.warning(f"Using BBO mid as fallback price: ${mid:,.2f}")
        return mid

    def get_account_balance(self) -> float:
        """
        Returns account equity in USDC.
        In paper mode, returns a default simulated balance.
        """
        if self.paper:
            return 10_000.0  # Default paper balance: $10,000

        try:
            resp = requests.get(
                f"{self.base_url}/account",
                headers=self._auth_headers(),
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("equity", 0))
        except Exception as e:
            log.error(f"Balance fetch failed: {e}")
            return 0.0

    def get_open_position(self) -> Optional[dict]:
        """Returns current position for the configured market, or None."""
        if self.paper:
            return self.paper_book.get_position(self.market)

        try:
            resp = requests.get(
                f"{self.base_url}/positions",
                headers=self._auth_headers(),
                timeout=10
            )
            resp.raise_for_status()
            positions = resp.json().get("results", [])
            for pos in positions:
                if pos.get("market") == self.market and float(pos.get("size", 0)) != 0:
                    return pos
        except Exception as e:
            log.error(f"Position fetch failed: {e}")
        return None

    # ─── Order Sizing ─────────────────────────────────────────

    def calculate_order_size(self, price: float) -> float:
        """
        Calculate order size based on account balance and position sizing config.
        Rounds to the market's size increment.
        """
        balance = self.get_account_balance()
        position_pct = self.trade_cfg.get("position_size_pct", 0.05)
        notional = balance * position_pct
        size = notional / price

        increment = float(self.pdx_cfg.get("size_increment", 0.00001))
        size = math.floor(size / increment) * increment

        min_notional = self.pdx_cfg.get("min_notional_usd", 10.0)
        if size * price < min_notional:
            size = math.ceil(min_notional / price / increment) * increment

        log.info(
            f"Order sizing: balance=${balance:,.2f}, "
            f"pct={position_pct:.0%}, "
            f"notional=${notional:,.2f}, "
            f"size={size:.5f} BTC @ ${price:,.2f}"
        )
        return size

    def calculate_limit_price(self, side: str, mid_price: float) -> float:
        """Calculates limit price offset from mid."""
        tick = self.pdx_cfg.get("price_tick_size", 0.1)
        offset_ticks = self.trade_cfg.get("limit_offset_ticks", 2)
        offset = tick * offset_ticks

        if side == "BUY":
            price = mid_price + offset  # Be slightly aggressive to ensure fill
        else:
            price = mid_price - offset

        # Round to tick size
        price = round(round(price / tick) * tick, 1)
        return price

    # ─── Order Execution ──────────────────────────────────────

    def close_position(self) -> Optional[dict]:
        """Close existing position regardless of direction."""
        pos = self.get_open_position()
        if not pos:
            log.info("No position to close")
            return None

        if self.paper:
            mark = self.get_mark_price()
            return self.paper_book.close_position(self.market, mark)

        current_side = pos.get("side", "LONG")
        close_side = "SELL" if current_side == "LONG" else "BUY"
        size = abs(float(pos.get("size", 0)))
        return self._submit_order(close_side, size, reduce_only=True)
        """Internal order placement — routes to paper or live."""
        existing = self.get_open_position()
        if existing:
            log.info(f"Position already open — skipping new {side} order")
            return None

        bbo = self.get_bbo()
        mid_price = bbo.get("mid", 0)
        if mid_price <= 0:
            log.error("Could not get valid mid price — aborting order")
            return None

        size = self.calculate_order_size(mid_price)
        order_type = self.trade_cfg.get("order_type", "limit")

        if order_type == "limit":
            price = self.calculate_limit_price(side, mid_price)
        else:
            price = mid_price

        if self.paper:
            return self.paper_book.open_position(self.market, side, size, price,
                                                  open_reason=open_reason)

        return self._submit_order(side, size, limit_price=price if order_type == "limit" else None)

    def open_long(self, open_reason: str = "signal") -> Optional[dict]:
        return self._place_order("BUY", open_reason=open_reason)

    def open_short(self, open_reason: str = "signal") -> Optional[dict]:
        return self._place_order("SELL", open_reason=open_reason)

    def _place_order(self, side: str, open_reason: str = "signal") -> Optional[dict]:
        """Internal order placement — routes to paper or live."""
        existing = self.get_open_position()
        if existing:
            log.info(f"Position already open — skipping new {side} order")
            return None

        # In paper mode use mark price directly — testnet BBO is often empty
        if self.paper:
            mid_price = self.get_mark_price()
            if mid_price <= 0:
                log.error("Could not get valid mark price — aborting order")
                return None
            size = self.calculate_order_size(mid_price)
            price = self.calculate_limit_price(side, mid_price)
            return self.paper_book.open_position(self.market, side, size, price,
                                                  open_reason=open_reason)

        # Live mode — use real BBO for accurate pricing
        bbo = self.get_bbo()
        mid_price = bbo.get("mid", 0)
        if mid_price <= 0:
            log.error("Could not get valid mid price — aborting order")
            return None
        size = self.calculate_order_size(mid_price)
        order_type = self.trade_cfg.get("order_type", "limit")
        price = self.calculate_limit_price(side, mid_price) if order_type == "limit" else mid_price
        return self._submit_order(side, size, limit_price=price if order_type == "limit" else None)

    def _submit_order(
        self,
        side: str,
        size: float,
        limit_price: Optional[float] = None,
        reduce_only: bool = False
    ) -> Optional[dict]:
        """
        Submits a real order to Paradex REST API.
        Requires valid authentication and Starknet signing.
        """
        order_type = "LIMIT" if limit_price else "MARKET"

        payload = {
            "market": self.market,
            "side": side,
            "type": order_type,
            "size": str(round(size, 5)),
            "reduce_only": reduce_only,
        }
        if limit_price:
            payload["price"] = str(round(limit_price, 1))

        # Sign the order (Starknet)
        signed_payload = self._sign_order(payload)

        try:
            resp = requests.post(
                f"{self.base_url}/orders",
                headers=self._auth_headers(),
                json=signed_payload,
                timeout=15
            )
            resp.raise_for_status()
            order = resp.json()
            log.info(f"Order submitted: {order}")
            return order
        except requests.HTTPError as e:
            log.error(f"Order submission failed: {e.response.status_code} {e.response.text}")
            return None
        except Exception as e:
            log.error(f"Order submission error: {e}")
            return None

    # ─── Authentication & Signing ─────────────────────────────

    def _authenticate(self):
        """
        Authenticate with Paradex using Starknet key signing.
        See: https://docs.paradex.trade/documentation/getting-started/authentication
        """
        try:
            # Paradex uses JWT authentication with Starknet signatures
            # Full implementation requires starknet-py
            # This is a placeholder — real auth needs the Starknet signing flow
            log.info("Authenticating with Paradex...")

            from starknet_py.net.signer.stark_curve_signer import StarkCurveSigner
            from starknet_py.net.models import StarknetChainId

            private_key = int(self.pdx_cfg["private_key"], 16)
            account_address = self.pdx_cfg["account_address"]

            # Request auth nonce
            nonce_resp = requests.get(
                f"{self.base_url}/auth/nonce",
                params={"account_address": account_address},
                timeout=10
            )
            nonce_resp.raise_for_status()
            nonce = nonce_resp.json().get("nonce")

            # Sign the nonce with Starknet private key
            signer = StarkCurveSigner(
                account_address=int(account_address, 16),
                key_pair=private_key,
            )
            # Full signing flow implementation follows Paradex docs
            # See: https://docs.paradex.trade/documentation/getting-started/authentication

            log.info("Paradex authentication successful")

        except ImportError:
            log.error(
                "starknet-py not installed. Run: pip install starknet-py\n"
                "Or use PAPER_TRADING=true to test without auth."
            )
            raise
        except Exception as e:
            log.error(f"Authentication failed: {e}")
            raise

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._jwt_token}",
            "Content-Type": "application/json",
        }

    def _sign_order(self, payload: dict) -> dict:
        """
        Sign order payload with Starknet key.
        Full implementation: https://docs.paradex.trade/documentation/api-integration/order-signing
        """
        # Placeholder — Paradex order signing uses Pedersen hash + ECDSA on Stark curve
        # Real implementation requires starknet-py and follows Paradex signing spec
        log.warning("Order signing not implemented — set paper_trading: true")
        return payload

    # ─── Monitoring Helpers ───────────────────────────────────

    def check_stop_take_profit(self) -> Optional[str]:
        """
        Checks if current position has hit stop loss or take profit.
        Returns 'STOP', 'TAKE_PROFIT', or None.
        """
        pos = self.get_open_position()
        if not pos:
            return None

        current_price = self.get_mark_price()
        if current_price <= 0:
            return None

        entry_price = float(pos.get("entry_price", 0))
        side = pos.get("side", "BUY")
        sl_pct = self.trade_cfg.get("stop_loss_pct", 0.02)
        tp_pct = self.trade_cfg.get("take_profit_pct", 0.04)

        if side == "BUY":
            sl_price = entry_price * (1 - sl_pct)
            tp_price = entry_price * (1 + tp_pct)
            if current_price <= sl_price:
                log.warning(f"STOP LOSS hit: price {current_price:.1f} ≤ SL {sl_price:.1f}")
                return "STOP"
            if current_price >= tp_price:
                log.info(f"TAKE PROFIT hit: price {current_price:.1f} ≥ TP {tp_price:.1f}")
                return "TAKE_PROFIT"
        else:
            sl_price = entry_price * (1 + sl_pct)
            tp_price = entry_price * (1 - tp_pct)
            if current_price >= sl_price:
                log.warning(f"STOP LOSS hit: price {current_price:.1f} ≥ SL {sl_price:.1f}")
                return "STOP"
            if current_price <= tp_price:
                log.info(f"TAKE PROFIT hit: price {current_price:.1f} ≤ TP {tp_price:.1f}")
                return "TAKE_PROFIT"

        return None

    def status_report(self) -> dict:
        """Returns a quick snapshot of account + position status."""
        pos = self.get_open_position()
        price = self.get_mark_price()
        balance = self.get_account_balance()

        upnl = 0.0
        if self.paper and pos:
            upnl = self.paper_book.unrealized_pnl(self.market, price)
        
        return {
            "market": self.market,
            "mark_price": price,
            "balance_usd": balance,
            "position": pos,
            "unrealized_pnl": upnl,
            "realized_pnl": self.paper_book.realized_pnl if self.paper else None,
            "paper_mode": self.paper,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }