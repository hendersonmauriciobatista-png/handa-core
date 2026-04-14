# ============================================================
# core/indicators/indicator_snapshot.py
# Estrutura que representa um snapshot de indicadores
# ============================================================

from dataclasses import dataclass


@dataclass
class IndicatorSnapshot:

    ema_10: float
    ema_20: float
    ema_50: float

    rsi_14: float

    volume_ratio: float

    price: float
