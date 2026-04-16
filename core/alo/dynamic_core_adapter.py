# ============================================================
# core/alo/dynamic_core_adapter.py
# H&A — ALO Dynamic Core Adapter
# Responsável por montar o input do núcleo dinâmico
# ============================================================

from core.alo.dynamic_core_models import (
    AloDynamicCoreInput,
    AloDynamicMarketContext,
    AloDynamicSetupContext,
    AloDynamicProfileContext,
    AloDynamicSystemContext,
)


class AloDynamicCoreAdapter:
    """
    Adapter responsável por transformar os dados do sistema
    no formato padrão do núcleo dinâmico.
    """

    def build_input(
        self,
        snapshot=None,
        profile=None,
        system_ctx=None,
        mqii_data=None,
    ) -> AloDynamicCoreInput:

        # ========================================================
        # SETUP CONTEXT
        # ========================================================
        setup = AloDynamicSetupContext(
            symbol=str(getattr(snapshot, "pair", "") or "").strip().upper(),
            price=float(getattr(snapshot, "price", 0.0) or 0.0),
            rsi=float(getattr(snapshot, "rsi", 0.0) or 0.0),
            volume_ratio=float(getattr(snapshot, "volume_ratio", 0.0) or 0.0),
            trend=str(getattr(snapshot, "trend", "") or "").strip().upper(),
            momentum=str(getattr(snapshot, "momentum", "") or "").strip().upper(),
            volume_state=str(getattr(snapshot, "volume_state", "") or "").strip().upper(),
            setup_quality_label=str(getattr(snapshot, "setup_quality_label", "") or "").strip().upper(),
            setup_quality_score=float(getattr(snapshot, "setup_quality_score", 0.0) or 0.0),
            market_score=float(getattr(snapshot, "market_score", 0.0) or 0.0),
        )

        # ========================================================
        # MARKET CONTEXT
        # ========================================================
        market = AloDynamicMarketContext()

        if isinstance(mqii_data, dict):
            market.market_state = str(mqii_data.get("state", "") or "").strip().upper()
            market.liquidity_score = float(mqii_data.get("liquidity_score", 0.0) or 0.0)
            market.liquidity_label = str(mqii_data.get("liquidity_label", "") or "").strip().upper()
            market.mqii_state = str(mqii_data.get("state", "") or "").strip().upper()
            market.mqii_score = float(mqii_data.get("score", 0.0) or 0.0)

        # ========================================================
        # PROFILE CONTEXT
        # ========================================================
        profile_ctx = AloDynamicProfileContext()

        if profile is not None:
            profile_ctx.status = str(getattr(profile, "status", "") or "").strip().upper()
            profile_ctx.confidence_score = float(getattr(profile, "confidence_score", 0.0) or 0.0)
            profile_ctx.total_events = int(getattr(profile, "total_events", 0) or 0)
            profile_ctx.execution_count = int(getattr(profile, "execution_count", 0) or 0)
            profile_ctx.non_execution_count = int(getattr(profile, "non_execution_count", 0) or 0)
            profile_ctx.structural_block_count = int(getattr(profile, "structural_block_count", 0) or 0)
            profile_ctx.quality_filter_count = int(getattr(profile, "quality_filter_count", 0) or 0)
            profile_ctx.low_score_count = int(getattr(profile, "low_score_count", 0) or 0)
            profile_ctx.loss_count = int(getattr(profile, "loss_count", 0) or 0)
            profile_ctx.win_count = int(getattr(profile, "win_count", 0) or 0)
            profile_ctx.block_bias = float(getattr(profile, "block_bias", 0.0) or 0.0)

        # ========================================================
        # SYSTEM CONTEXT
        # ========================================================
        system = AloDynamicSystemContext()

        if system_ctx is not None:
            system.active_slots = int(getattr(system_ctx, "active_slots", 0) or 0)
            system.max_slots = int(getattr(system_ctx, "max_slots", 4) or 4)
            system.balance = float(getattr(system_ctx, "balance", 0.0) or 0.0)
            system.loss_streak = int(getattr(system_ctx, "loss_streak", 0) or 0)
            system.win_rate_recent = float(getattr(system_ctx, "win_rate_recent", 0.0) or 0.0)
            system.drawdown_pct = float(getattr(system_ctx, "drawdown_pct", 0.0) or 0.0)

        # ========================================================
        # FINAL INPUT
        # ========================================================
        return AloDynamicCoreInput(
            symbol=setup.symbol,
            market=market,
            setup=setup,
            profile=profile_ctx,
            system=system,
        )