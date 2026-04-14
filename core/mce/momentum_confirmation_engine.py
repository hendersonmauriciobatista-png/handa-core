# ============================================================
# MOMENTUM CONFIRMATION ENGINE (MCE)
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
        analysis = token.get("analysis", {})

        price = float(analysis.get("price", 0))
        volume_ratio = float(analysis.get("volume_ratio", 0))
        rsi = float(analysis.get("rsi", 50))

        candidate = MCECandidate(
            symbol=symbol,
            reference_price=price,
            reference_volume_ratio=volume_ratio,
            reference_rsi=rsi,
            armed_cycle=self.current_cycle,
        )

        self.active_candidates[symbol] = candidate

        print(f"[MCE] ARMADO: {symbol}")

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

            price = float(data.get("price", 0))
            volume_ratio = float(data.get("volume_ratio", 0))
            rsi = float(data.get("rsi", 50))
            momentum = data.get("momentum")

            # ---------------------------
            # CANCELAMENTOS
            # ---------------------------
            if rsi >= MCE_HARD_RSI_LIMIT:
                candidate.status = MCEStatus.CANCELLED
                removed.append(symbol)
                continue

            if momentum == "BEARISH":
                candidate.status = MCEStatus.CANCELLED
                removed.append(symbol)
                continue

            # ---------------------------
            # EXPIRAÇÃO
            # ---------------------------
            if self.current_cycle - candidate.armed_cycle > MCE_CONFIRMATION_CYCLES:
                candidate.status = MCEStatus.EXPIRED
                removed.append(symbol)
                continue

            # ---------------------------
            # CONFIRMAÇÃO
            # ---------------------------
            price_change = (price - candidate.reference_price) / candidate.reference_price * 100

            volume_ok = volume_ratio >= candidate.reference_volume_ratio * MCE_MIN_VOLUME_RETENTION

            if (
                price_change >= MCE_MIN_PRICE_PROGRESS
                and volume_ok
                and rsi <= MCE_MAX_RSI
                and momentum in ["NEUTRAL", "BULLISH"]
            ):
                candidate.status = MCEStatus.CONFIRMED
                confirmed.append(symbol)
                removed.append(symbol)

        # limpar candidatos finalizados
        for symbol in removed:
            self.active_candidates.pop(symbol, None)

        return confirmed