# ============================================================
# MOMENTUM CONFIRMATION ENGINE (MCE)
# H&A — confirmação de entrada por ciclos
# ============================================================

from core.mce.mce_models import MCECandidate, MCEStatus
from core.mce.mce_config import *


class MomentumConfirmationEngine:

    def __init__(self):
        self.active_candidates = {}
        self.current_cycle = 0

    # ========================================================
    # ARMAR CANDIDATO
    # ========================================================
    def arm(self, token):
        symbol = token.get("symbol")
        analysis = token.get("analysis", {}) or {}

        if not symbol:
            return None

        price = float(analysis.get("price", 0) or 0)
        volume_ratio = float(analysis.get("volume_ratio", 0) or 0)
        rsi = float(analysis.get("rsi", 50) or 50)

        if price <= 0:
            return None

        candidate = MCECandidate(
            symbol=symbol,
            reference_price=price,
            reference_volume_ratio=volume_ratio,
            reference_rsi=rsi,
            armed_cycle=self.current_cycle,
        )

        self.active_candidates[symbol] = candidate

        print(f"[MCE] ARMADO: {symbol}")
        return candidate

    # ========================================================
    # CONFIRMAR CANDIDATO — COMPATIBILIDADE COM RADAR
    # ========================================================
    def confirm(self, token):
        symbol = token.get("symbol")
        analysis = token.get("analysis", {}) or {}

        if not symbol:
            return False

        symbol = str(symbol).strip().upper()

        if symbol not in self.active_candidates:
            self.arm(token)
            return False

        market_data = {
            symbol: {
                "price": float(analysis.get("price", 0) or 0),
                "volume_ratio": float(analysis.get("volume_ratio", 0) or 0),
                "rsi": float(analysis.get("rsi", 50) or 50),
                "momentum": self._normalize_value(analysis.get("momentum")),
            }
        }

        confirmed = self.update(market_data)

        if symbol in confirmed:
            print(f"[MCE] CONFIRMADO: {symbol}")
            return True

        return False

    # ========================================================
    # ATUALIZAR CANDIDATOS
    # ========================================================
    def update(self, market_data):
        self.current_cycle += 1

        confirmed = []
        removed = []

        for symbol, candidate in list(self.active_candidates.items()):

            data = market_data.get(symbol)

            if not data:
                continue

            price = float(data.get("price", 0) or 0)
            volume_ratio = float(data.get("volume_ratio", 0) or 0)
            rsi = float(data.get("rsi", 50) or 50)
            momentum = self._normalize_value(data.get("momentum"))

            if price <= 0 or candidate.reference_price <= 0:
                candidate.status = MCEStatus.CANCELLED
                removed.append(symbol)
                continue

            # ---------------------------
            # CANCELAMENTOS
            # ---------------------------
            if rsi >= MCE_HARD_RSI_LIMIT:
                candidate.status = MCEStatus.CANCELLED
                removed.append(symbol)
                print(f"[MCE] CANCELADO RSI: {symbol}")
                continue

            if momentum == "BEARISH":
                candidate.status = MCEStatus.CANCELLED
                removed.append(symbol)
                print(f"[MCE] CANCELADO BEARISH: {symbol}")
                continue

            # ---------------------------
            # EXPIRAÇÃO
            # ---------------------------
            if self.current_cycle - candidate.armed_cycle > MCE_CONFIRMATION_CYCLES:
                candidate.status = MCEStatus.EXPIRED
                removed.append(symbol)
                print(f"[MCE] EXPIRADO: {symbol}")
                continue

            # ======================================================
            # 🔥 MCE V3.1 — CONFIRMAÇÃO DE CONTINUIDADE
            # ======================================================

            price_change = (
                (price - candidate.reference_price) / candidate.reference_price * 100
            )

            volume_ok = (
                volume_ratio
                >= candidate.reference_volume_ratio * MCE_MIN_VOLUME_RETENTION
            )

            # 🔥 MCE V3.2 — PROGRESSO DINÂMICO CONTEXTUAL
            # Ajusta a sensibilidade conforme momentum, volume e RSI.
            # Objetivo: reduzir overfilter sem liberar entrada fraca.

            progress_ratio = (
                price / candidate.reference_price
                if candidate.reference_price > 0
                else 1.0
            )

            dynamic_progress_min = 1.00035  # padrão conservador (~0.10%)

            if momentum == "BULLISH":
                dynamic_progress_min = 1.00008  # bullish confirma com menor avanço

            elif momentum == "NEUTRAL" and volume_ratio >= 2.0 and 40 <= rsi <= 58:
                dynamic_progress_min = 1.00015  # neutral premium

            elif momentum == "NEUTRAL" and volume_ratio >= 0.9 and 42 <= rsi <= 58:
                dynamic_progress_min = 1.00020
            progress_ok = progress_ratio >= dynamic_progress_min

            print(
                f"[MCE V3.2] {symbol} progresso dinâmico | "
                f"ratio={progress_ratio:.6f} | min={dynamic_progress_min:.6f} | "
                f"momentum={momentum} | vol={volume_ratio:.3f} | rsi={rsi:.2f}"
            )

            # 🔥 NOVO: impedir perda de força (volume caindo demais)
            print(
                f"[MCE V3.2 EXPLAIN] {symbol} | "
                f"price={price:.8f} | reference_price={candidate.reference_price:.8f} | "
                f"price_change={price_change:.6f}% | "
                f"progress_ok={progress_ok} | "
                f"volume_ok={volume_ok} | "
                f"volume_ratio={volume_ratio:.3f} | "
                f"reference_volume_ratio={candidate.reference_volume_ratio:.3f} | "
                f"rsi_ok={rsi <= MCE_MAX_RSI} | "
                f"momentum_ok={momentum in ['NEUTRAL', 'BULLISH']}"
            )

            volume_drop = volume_ratio < (candidate.reference_volume_ratio * 0.7)

            if volume_drop:
                candidate.status = MCEStatus.CANCELLED
                removed.append(symbol)
                print(f"[MCE] CANCELADO VOLUME DROP: {symbol}")
                continue

            if (
                price_change >= MCE_MIN_PRICE_PROGRESS
                and progress_ok
                and volume_ok
                and rsi <= MCE_MAX_RSI
                and momentum in ["NEUTRAL", "BULLISH"]
            ):
                candidate.status = MCEStatus.CONFIRMED
                confirmed.append(symbol)
                removed.append(symbol)
                continue

        for symbol in removed:
            self.active_candidates.pop(symbol, None)

        return confirmed

    # ========================================================
    # NORMALIZAÇÃO
    # ========================================================
    def _normalize_value(self, value):
        if value is None:
            return ""

        if hasattr(value, "value"):
            return str(value.value).strip().upper()

        raw = str(value).strip()

        if "." in raw:
            raw = raw.split(".")[-1]

        return raw.upper()
