# ============================================================
# core/alo/dynamic_core_engine.py
# H&A — ALO Dynamic Core Engine
# Motor inicial do núcleo dinâmico do ALO
# ============================================================

from core.alo.dynamic_core_models import (
    AloDynamicCoreInput,
    AloDynamicCoreOutput,
)


class AloDynamicCoreEngine:
    """
    Núcleo dinâmico inicial do ALO.

    Objetivo:
    - consolidar histórico + setup + macro + sistema
    - transformar isso em modo operacional contextual
    - preparar a substituição futura do veto binário
    """

    def evaluate(self, data: AloDynamicCoreInput) -> AloDynamicCoreOutput:
        reasons = []

        symbol = str(data.symbol or "").strip().upper()

        market = data.market
        setup = data.setup
        profile = data.profile
        system = data.system

        score = 0.0

        # ========================================================
        # 1. SETUP ATUAL (peso alto)
        # ========================================================
        setup_quality_score = float(setup.setup_quality_score or 0.0)
        score += min(max(setup_quality_score, 0.0), 10.0)

        reasons.append(f"SETUP_QUALITY_SCORE={setup_quality_score:.4f}")

        # trend
        trend = str(setup.trend or "").strip().upper()
        if trend.endswith("UPTREND"):
            score += 1.5
            reasons.append("TREND_UPTREND")
        elif trend:
            score -= 0.5
            reasons.append(f"TREND_{trend}")

        # momentum
        momentum = str(setup.momentum or "").strip().upper()
        if momentum.endswith("BULLISH"):
            score += 1.5
            reasons.append("MOMENTUM_BULLISH")
        elif momentum:
            score -= 0.5
            reasons.append(f"MOMENTUM_{momentum}")

        # volume
        volume_state = str(setup.volume_state or "").strip().upper()
        volume_ratio = float(setup.volume_ratio or 0.0)

        if volume_state == "HIGH":
            score += 1.5
            reasons.append("VOLUME_HIGH")
        elif volume_ratio >= 1.2:
            score += 1.0
            reasons.append(f"VOLUME_RATIO_OK={volume_ratio:.3f}")
        elif volume_ratio < 0.9:
            score -= 1.0
            reasons.append(f"VOLUME_RATIO_LOW={volume_ratio:.3f}")

        # RSI
        rsi = float(setup.rsi or 0.0)
        if 48.0 <= rsi <= 68.0:
            score += 1.5
            reasons.append(f"RSI_OK={rsi:.2f}")
        elif 68.0 < rsi <= 74.0:
            score += 0.5
            reasons.append(f"RSI_ELEVADO_CONTROLADO={rsi:.2f}")
        elif rsi > 74.0:
            score -= 1.0
            reasons.append(f"RSI_ESTICADO={rsi:.2f}")
        elif 0.0 < rsi < 45.0:
            score -= 1.0
            reasons.append(f"RSI_FRACO={rsi:.2f}")

        # ========================================================
        # 2. CONTEXTO DE MERCADO (peso médio-alto)
        # ========================================================
        market_state = str(market.market_state or "").strip().upper()
        liquidity_score = float(market.liquidity_score or 0.0)
        mqii_state = str(market.mqii_state or "").strip().upper()
        mqii_score = float(market.mqii_score or 0.0)

        if market_state in ("BULLISH_STRONG", "AGGRESSIVE_OK", "TRADE_OK"):
            score += 2.0
            reasons.append(f"MARKET_STATE_OK={market_state}")
        elif market_state in ("CAUTIOUS", "NEUTRAL", "NEUTRO_OPERAVEL"):
            score += 0.5
            reasons.append(f"MARKET_STATE_CAUTION={market_state}")
        elif market_state in ("NO_TRADE", "LATERAL_FRACO", "UNKNOWN"):
            score -= 2.0
            reasons.append(f"MARKET_STATE_BAD={market_state}")

        if liquidity_score >= 0.70:
            score += 1.5
            reasons.append(f"LIQUIDITY_STRONG={liquidity_score:.3f}")
        elif liquidity_score >= 0.50:
            score += 1.0
            reasons.append(f"LIQUIDITY_OK={liquidity_score:.3f}")
        elif 0.0 < liquidity_score < 0.30:
            score -= 0.75
            reasons.append(f"LIQUIDITY_WEAK={liquidity_score:.3f}")

        if mqii_state in ("AGGRESSIVE_OK", "TRADE_OK"):
            score += 1.0
            reasons.append(f"MQII_OK={mqii_state}")
        elif mqii_state == "CAUTIOUS" and mqii_score >= 0.30:
            score += 0.25
            reasons.append(f"MQII_CAUTIOUS_OK={mqii_score:.3f}")
        elif mqii_state == "NO_TRADE":
            score -= 2.0
            reasons.append("MQII_NO_TRADE")

        # ========================================================
        # 3. HISTÓRICO DO ATIVO (peso moderado, não soberano)
        # ========================================================
        historical_conf = float(profile.confidence_score or 0.0)
        status = str(profile.status or "").strip().upper()
        total_events = int(profile.total_events or 0)
        block_bias = float(profile.block_bias or 0.0)
        loss_count = int(profile.loss_count or 0)
        win_count = int(profile.win_count or 0)

        if total_events >= 10:
            if historical_conf >= 0.75:
                score += 1.5
                reasons.append(f"HISTORY_STRONG={historical_conf:.2f}")
            elif historical_conf >= 0.50:
                score += 0.75
                reasons.append(f"HISTORY_OK={historical_conf:.2f}")
            elif historical_conf < 0.30:
                score -= 1.0
                reasons.append(f"HISTORY_WEAK={historical_conf:.2f}")
        else:
            reasons.append(f"HISTORY_LIGHT_WEIGHT={total_events}")

        if block_bias >= 0.75:
            score -= 0.75
            reasons.append(f"BLOCK_BIAS_HIGH={block_bias:.2f}")
        elif block_bias >= 0.50:
            score -= 0.40
            reasons.append(f"BLOCK_BIAS_MODERATE={block_bias:.2f}")

        if loss_count > win_count and loss_count >= 3:
            score -= 0.75
            reasons.append(
                f"HISTORY_LOSS_PRESSURE=loss:{loss_count}|win:{win_count}"
            )

        # ========================================================
        # 4. ESTADO SISTÊMICO (peso defensivo)
        # ========================================================
        loss_streak = int(system.loss_streak or 0)
        drawdown_pct = float(system.drawdown_pct or 0.0)
        active_slots = int(system.active_slots or 0)
        max_slots = int(system.max_slots or 4)

        if loss_streak >= 3:
            score -= 1.5
            reasons.append(f"SYSTEM_LOSS_STREAK={loss_streak}")
        elif loss_streak == 2:
            score -= 0.75
            reasons.append(f"SYSTEM_LOSS_STREAK={loss_streak}")

        if drawdown_pct >= 0.03:
            score -= 1.5
            reasons.append(f"SYSTEM_DRAWDOWN={drawdown_pct:.4f}")
        elif drawdown_pct >= 0.015:
            score -= 0.5
            reasons.append(f"SYSTEM_DRAWDOWN={drawdown_pct:.4f}")

        if max_slots > 0 and active_slots >= max_slots:
            score -= 1.0
            reasons.append("SYSTEM_FULL_CAPACITY")

        # ========================================================
        # 5. CLASSIFICAÇÃO DINÂMICA
        # ========================================================
        premium_setup = (
            trend.endswith("UPTREND")
            and momentum.endswith("BULLISH")
            and (volume_state == "HIGH" or volume_ratio >= 1.2)
            and market_state in ("BULLISH_STRONG", "AGGRESSIVE_OK", "TRADE_OK")
        )

        override_permission = False
        block_reason = ""

        if score >= 11.0:
            dynamic_mode = "PREMIUM_OK"
            confidence_label = "ALTA"
            risk_weight = 1.20

        elif score >= 8.0:
            dynamic_mode = "TRADE_OK"
            confidence_label = "MODERADA"
            risk_weight = 1.00

        elif score >= 5.0:
            dynamic_mode = "CAUTION"
            confidence_label = "BAIXA"
            risk_weight = 0.80

        else:
            dynamic_mode = "BLOCK"
            confidence_label = "MUITO_BAIXA"
            risk_weight = 0.60
            block_reason = "SCORE_DINAMICO_INSUFICIENTE"

        # ========================================================
        # 6. OVERRIDE CONTEXTUAL
        # ========================================================
        if dynamic_mode == "BLOCK" and premium_setup and score >= 4.0:
            dynamic_mode = "CAUTION"
            confidence_label = "BAIXA"
            override_permission = True
            block_reason = ""
            reasons.append("CONTEXTUAL_PREMIUM_OVERRIDE")

        if status in ("BLOCKED", "REJECTED") and dynamic_mode in ("TRADE_OK", "PREMIUM_OK"):
            override_permission = True
            reasons.append(f"HISTORICAL_STATUS_REBAIXADO={status}")

        reasons.append(f"DYNAMIC_SCORE={score:.4f}")
        reasons.append(f"DYNAMIC_MODE={dynamic_mode}")

        return AloDynamicCoreOutput(
            symbol=symbol,
            dynamic_mode=dynamic_mode,
            confidence_score=round(score, 4),
            confidence_label=confidence_label,
            risk_weight=risk_weight,
            override_permission=override_permission,
            block_reason=block_reason,
            reasons=reasons,
        )