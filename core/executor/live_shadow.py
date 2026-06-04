# ============================================================
# core/executor/live_shadow.py
# LIVE SHADOW MODE v1
# Telemetria simulada de execucao live sem efeito operacional.
# ============================================================

try:
    from core.config.trading_config import (
        SHADOW_MODE_ENABLED,
        SHADOW_FEE_PCT,
        SHADOW_SLIPPAGE_PCT,
        SHADOW_LATENCY_MS,
    )
except Exception:
    SHADOW_MODE_ENABLED = True
    SHADOW_FEE_PCT = 0.10
    SHADOW_SLIPPAGE_PCT = 0.05
    SHADOW_LATENCY_MS = 500


class LiveShadowSimulator:
    """
    Simulador passivo para comparar execucao MOCK com execucao LIVE estimada.

    Nao envia ordens, nao altera posicao oficial e nao interfere no MockExecutor.
    """

    def __init__(
        self,
        enabled: bool = SHADOW_MODE_ENABLED,
        fee_pct: float = SHADOW_FEE_PCT,
        slippage_pct: float = SHADOW_SLIPPAGE_PCT,
        latency_ms: int = SHADOW_LATENCY_MS,
    ):
        self.enabled = bool(enabled)
        self.fee_pct = float(fee_pct)
        self.slippage_pct = float(slippage_pct)
        self.latency_ms = int(latency_ms)
        self.shadow_positions = {}
        print(
            f"[SHADOW INIT] enabled={self.enabled} | "
            f"fee_pct={self.fee_pct:g} | "
            f"slippage_pct={self.slippage_pct:g} | "
            f"latency_ms={self.latency_ms} | no_effect=True"
        )

    def record_buy(
        self,
        symbol: str,
        signal_price: float,
        allocated_usdc: float,
        quantity: float,
    ):
        if not self.enabled:
            return None

        symbol = str(symbol).strip().upper()
        signal_price = float(signal_price)
        allocated_usdc = float(allocated_usdc)
        quantity = float(quantity)

        shadow_entry_price = self._apply_buy_slippage(signal_price)
        self.shadow_positions[symbol] = {
            "symbol": symbol,
            "signal_price": signal_price,
            "shadow_entry_price": shadow_entry_price,
            "allocated_usdc": allocated_usdc,
            "quantity": quantity,
        }

        telemetry = {
            "symbol": symbol,
            "signal_price": signal_price,
            "shadow_entry_price": shadow_entry_price,
            "simulated_slippage_pct": self.slippage_pct,
            "simulated_fee_pct": self.fee_pct,
            "simulated_latency_ms": self.latency_ms,
            "no_effect": True,
        }

        self._log_buy(telemetry)
        return telemetry

    def record_sell(
        self,
        symbol: str,
        signal_entry_price: float,
        signal_exit_price: float,
        quantity: float,
        mock_net_pnl_usdc: float,
    ):
        if not self.enabled:
            return None

        symbol = str(symbol).strip().upper()
        signal_entry_price = float(signal_entry_price)
        signal_exit_price = float(signal_exit_price)
        quantity = float(quantity)
        mock_net_pnl_usdc = float(mock_net_pnl_usdc)

        shadow_position = self.shadow_positions.pop(symbol, None) or {}
        shadow_entry_price = float(
            shadow_position.get(
                "shadow_entry_price",
                self._apply_buy_slippage(signal_entry_price),
            )
        )
        shadow_exit_price = self._apply_sell_slippage(signal_exit_price)

        entry_notional = quantity * shadow_entry_price
        exit_notional = quantity * shadow_exit_price
        gross_pnl_usdc = exit_notional - entry_notional
        gross_pnl_pct = (
            (gross_pnl_usdc / entry_notional) * 100
            if entry_notional > 0
            else 0.0
        )

        entry_fee_usdc = entry_notional * (self.fee_pct / 100)
        exit_fee_usdc = exit_notional * (self.fee_pct / 100)
        net_pnl_usdc = gross_pnl_usdc - entry_fee_usdc - exit_fee_usdc
        net_pnl_pct = (
            (net_pnl_usdc / entry_notional) * 100
            if entry_notional > 0
            else 0.0
        )
        mock_vs_shadow_delta = net_pnl_usdc - mock_net_pnl_usdc
        shadow_result = self._classify_result(net_pnl_usdc)

        telemetry = {
            "symbol": symbol,
            "signal_entry_price": signal_entry_price,
            "signal_exit_price": signal_exit_price,
            "shadow_entry_price": shadow_entry_price,
            "shadow_exit_price": shadow_exit_price,
            "simulated_slippage_pct": self.slippage_pct,
            "simulated_fee_pct": self.fee_pct,
            "simulated_latency_ms": self.latency_ms,
            "gross_pnl_pct": gross_pnl_pct,
            "net_pnl_pct": net_pnl_pct,
            "gross_pnl_usdc": gross_pnl_usdc,
            "net_pnl_usdc": net_pnl_usdc,
            "mock_vs_shadow_delta": mock_vs_shadow_delta,
            "shadow_result": shadow_result,
            "no_effect": True,
        }

        self._log_sell(telemetry)
        return telemetry

    def _apply_buy_slippage(self, price: float) -> float:
        return float(price) * (1 + (self.slippage_pct / 100))

    def _apply_sell_slippage(self, price: float) -> float:
        return float(price) * (1 - (self.slippage_pct / 100))

    def _classify_result(self, net_pnl_usdc: float) -> str:
        if net_pnl_usdc > 0:
            return "WIN"
        if net_pnl_usdc < 0:
            return "LOSS"
        return "BREAKEVEN"

    def _log_buy(self, telemetry: dict):
        print("[SHADOW BUY]")
        print(f"symbol={telemetry['symbol']}")
        print(f"signal_price={telemetry['signal_price']:.8f}")
        print(f"shadow_entry_price={telemetry['shadow_entry_price']:.8f}")
        print(f"slippage_pct={telemetry['simulated_slippage_pct']:.4f}")
        print(f"fee_pct={telemetry['simulated_fee_pct']:.4f}")
        print(f"latency_ms={telemetry['simulated_latency_ms']}")
        print(f"no_effect={telemetry['no_effect']}")

    def _log_sell(self, telemetry: dict):
        print("[SHADOW SELL]")
        print(f"symbol={telemetry['symbol']}")
        print(f"signal_entry_price={telemetry['signal_entry_price']:.8f}")
        print(f"signal_exit_price={telemetry['signal_exit_price']:.8f}")
        print(f"shadow_entry_price={telemetry['shadow_entry_price']:.8f}")
        print(f"shadow_exit_price={telemetry['shadow_exit_price']:.8f}")
        print(f"gross_pnl_pct={telemetry['gross_pnl_pct']:.6f}")
        print(f"net_pnl_pct={telemetry['net_pnl_pct']:.6f}")
        print(f"gross_pnl_usdc={telemetry['gross_pnl_usdc']:.6f}")
        print(f"net_pnl_usdc={telemetry['net_pnl_usdc']:.6f}")
        print(f"mock_vs_shadow_delta={telemetry['mock_vs_shadow_delta']:.6f}")
        print(f"shadow_result={telemetry['shadow_result']}")
        print(f"no_effect={telemetry['no_effect']}")
