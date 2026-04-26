from core.alo_intelligence.alo_core import ALOIntelligentCore
from core.alo_intelligence.alo_models import (
    ALOMode,
    TechnicalContext,
    MacroMarketContext,
    MemoryContext,
    TemporalContext,
    StructuralContext,
    WebContext,
)

alo = ALOIntelligentCore(mode=ALOMode.ADVISORY)

technical = TechnicalContext(
    price=2.5,
    rsi=52,
    ema_fast=2.49,
    ema_slow=2.48,
    ema_trend=2.47,
    volume_ratio=1.1,
    trend="UPTREND",
    momentum="NEUTRAL",
    market_state="SIDEWAYS",
    selection_score=0.78,
)

macro = MacroMarketContext(
    liquidity_score=0.5,
    liquidity_label="MODERADA",
    liquidity_message="Teste",
    avg_volume_ratio=1.0,
    uptrend_count=5,
    refined_count=30,
    approved_count=3,
    total_assets=40,
)

memory = MemoryContext(stagnation_count_recent=1)

temporal = TemporalContext(minutes_since_last_trade=30)

structural = StructuralContext()

web = WebContext()

result = alo.evaluate(
    symbol="TESTUSDC",
    technical=technical,
    macro=macro,
    memory=memory,
    temporal=temporal,
    structural=structural,
    web=web,
)

print(result)