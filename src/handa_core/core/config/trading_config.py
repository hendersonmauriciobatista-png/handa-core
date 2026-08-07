# ============================================================
# H&A — TRADING CONFIG (LUCRO DINÂMICO NÍVEL 2)
# PERFIL: AGRESSIVO COM CONTROLES
# ============================================================

# =========================
# TAXAS
# =========================
TAKER_FEE = 0.001
MAKER_FEE = 0.001
TOTAL_ROUND_TRIP_FEE = TAKER_FEE + MAKER_FEE  # 0.2%

# =========================
# LUCRO BASE
# =========================
MIN_PROFIT_PCT = 0.003   # 0.3% mínimo líquido desejado
MIN_PROFIT_AFTER_FEES = TOTAL_ROUND_TRIP_FEE + MIN_PROFIT_PCT

# =========================
# CAPITAL
# =========================
MIN_TRADE_USDC = 10.0
IDEAL_TRADE_USDC = 17.0
MAX_TRADE_USDC = 50.0

# =========================
# POSIÇÕES
# =========================
MAX_OPEN_POSITIONS = 4
MAX_PORTFOLIO_EXPOSURE = 0.60
CAPITAL_PER_SLOT_PCT = 0.15

# =========================
# FILTRO DE PARES
# =========================
MIN_VOLUME_24H_USDC = 50_000_000
MIN_PRICE_USDC = 0.01
MAX_SPREAD_PCT = 0.005

BLOCKED_QUOTE_ASSETS = ["BUSD", "TUSD", "DAI"]
BLOCKED_KEYWORDS = []

WHITELIST_PAIRS = []
BLACKLIST_PAIRS = []

# =========================
# MOMENTUM / TENDÊNCIA
# =========================
RSI_PERIOD = 14
RSI_OVERSOLD = 45
RSI_OVERBOUGHT = 70

EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 50

VOLUME_SURGE_MULTIPLIER = 2.0

ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 1.5
ATR_TARGET_MULTIPLIER = 2.5

# =========================
# STOP / TAKE BASE (FALLBACK)
# Não serão mais o cérebro principal.
# Servem como proteção máxima.
# =========================
STOP_LOSS_PCT = 0.006       # 0.6%
TAKE_PROFIT_PCT = 0.012     # 1.2%

TRAILING_STOP_PCT = 0.0035
TRAILING_ACTIVATION_PCT = 0.005

# =========================
# TIMEFRAMES
# =========================
PRIMARY_TIMEFRAME = "15m"
CONFIRM_TIMEFRAME = "1h"
ENTRY_TIMEFRAME = "5m"

# =========================
# PROTEÇÃO GERAL
# =========================
MAX_CONSECUTIVE_LOSSES = 3
COOLDOWN_AFTER_LOSSES_MIN = 30
MAX_DAILY_LOSS_PCT = 0.03

# ============================================================
# LUCRO DINÂMICO NÍVEL 2
# PERFIL: AGRESSIVO COM CONTROLES
# ============================================================

DYNAMIC_EXIT_ENABLED = True

# -------------------------
# FASE 1 — SEGURAR RUÍDO INICIAL
# -------------------------
MIN_HOLD_CYCLES = 3
MIN_HOLD_PNL_FOR_EARLY_EXIT = -0.0025   # -0.25%

# -------------------------
# FASE 2 — ARMAR PROTEÇÃO DE LUCRO
# -------------------------
PROFIT_ARM_LEVEL_1 = 0.0025   # +0.25%
PROFIT_ARM_LEVEL_2 = 0.0045   # +0.45%
PROFIT_ARM_LEVEL_3 = 0.0070   # +0.70%

# quanto pode devolver desde o pico
PROFIT_GIVEBACK_LEVEL_1 = 0.0012   # 0.12%
PROFIT_GIVEBACK_LEVEL_2 = 0.0018   # 0.18%
PROFIT_GIVEBACK_LEVEL_3 = 0.0022   # 0.22%

# -------------------------
# FASE 3 — FORÇA PARA CONTINUAR SEGURANDO
# -------------------------
MIN_RSI_TO_HOLD = 50
WEAK_RSI_LEVEL = 48
HARD_WEAK_RSI_LEVEL = 44

MIN_VOLUME_RATIO_TO_HOLD = 0.85
STRONG_VOLUME_RATIO = 1.20

MIN_PNL_TO_KEEP_AGGRESSIVE = 0.0030   # +0.30%

# -------------------------
# FASE 4 — CORTE DE LATERALIZAÇÃO
# -------------------------
STAGNATION_CYCLES = 8
STAGNATION_MAX_PNL = 0.0010          # +0.10%
STAGNATION_MIN_PNL = -0.0025         # -0.25%

# -------------------------
# FASE 5 — SAÍDA POR FRAQUEZA
# -------------------------
EXIT_ON_EMA_LOSS = True
EXIT_ON_RSI_LOSS = True
EXIT_ON_VOLUME_FADE = True

# perda estrutural mínima para saída
ALLOW_WEAKNESS_EXIT_AFTER_CYCLES = 3

# -------------------------
# FASE 6 — PROTEÇÃO ANTI-DEVOLUÇÃO
# -------------------------
BREAKEVEN_PROTECTION_ENABLED = True
BREAKEVEN_TRIGGER_PNL = 0.0030       # +0.30%
BREAKEVEN_FLOOR_PNL = 0.0005         # +0.05%

# -------------------------
# FASE 7 — HARD EXIT
# -------------------------
HARD_EXIT_MAX_LOSS = -0.0060         # -0.60%
HARD_EXIT_ON_TREND_BREAK = True
HARD_EXIT_ON_DOUBLE_WEAKNESS = True

# dupla fraqueza = ex:
# EMA curta perde EMA longa + RSI abaixo do limite duro