# ============================================================
# core/slot_controller.py
# Controlador central dos slots de trading (H&A SAFE COMPAT)
# BUY PASSANDO PELO DECISION ENGINE
# SELL CENTRALIZADO VIA POSITION MANAGER
# VARREDURA CONTROLADA E SEM REPETIÇÃO DO MESMO SÍMBOLO NO CICLO
# + BLOQUEIO CURTO PÓS-REJEIÇÃO ENTRE CICLOS
# + INTEGRAÇÃO DINÂMICA DE CONTEXTO OPERACIONAL
# + H&A LEARNING SYNC (RADAR + DECISION ENGINE)
# ============================================================

import time
from typing import List

from core.slot import Slot
from core.capital_engine.capital_allocator import CapitalAllocator
from core.position.position_manager import CloseReason
from core.decision.decision_engine import MarketSnapshot
from core.learning.adaptive_learning_observer import AdaptiveLearningObserver
from core.notifications.telegram_notifier import TelegramNotifier


class SlotController:

    def __init__(
        self,
        slot_ids: List[int],
        decision_engine=None,
        client=None,
        executor=None,
        risk_manager=None,
        symbol: str = "BTCUSDC",
        cooldown: float = 2.0,
        alo=None,
    ):
        self.symbol = symbol
        self.cooldown = cooldown
        self.cooldown_win = 10 * 60  # 10 minutos (bloqueio pós WIN)

        self.client = client
        self.executor = executor
        self.risk_manager = risk_manager
        self._decision_engine = decision_engine

        self.market_radar = None
        self.position_manager = None
        self.lc1_adapter = None

        # CAPITAL
        self.capital_allocator = (
            CapitalAllocator(self.executor) if self.executor else None
        )

        # CONTROLE FINANCEIRO / ESTADO GLOBAL
        self.balance = 0.0
        self.boot_balance = 0.0
        self.peak_balance = 0.0
        self.profit_today = 0.0
        self.profit_total = 0.0
        self.trade_history = []

        # SLOTS
        self._slots = {slot_id: Slot(slot_id) for slot_id in slot_ids}

        self._cycle_counter = 0

        # COOLDOWN / REINCIDÊNCIA POR PAR (BASEADO EM TEMPO / LOSS REAL)
        self.pair_cooldowns = {}
        self.pair_loss_streak = {}
        self.pair_last_loss_at = {}

        self.cooldown_loss_1 = 30 * 60
        self.cooldown_loss_2 = 2 * 60 * 60
        self.cooldown_loss_3 = 12 * 60 * 60

        self.loss_streak_reset_window = 12 * 60 * 60

        # DRC — Dynamic Reentry Control
        self.drc_fast_stop_seconds = 15
        self.drc_quick_stop_seconds = 30
        self.drc_exhaustion_profit_pct = 0.03
        self.drc_good_profit_pct = 0.007
        self.drc_fast_stop_cooldown = 45 * 60
        self.drc_quick_stop_cooldown = 20 * 60
        self.drc_exhaustion_cooldown = 20 * 60
        self.drc_good_profit_cooldown = 12 * 60

        # BLOQUEIO CURTO ENTRE CICLOS (NEGATIVA / FALHA DE BUY)
        self.rejected_symbols_cooldown = {}

        # ========================================================
        # H&A LEARNING — COOLDOWN ADAPTATIVO (CONTROLADO)
        # ========================================================

        self.learning_enabled = True  # master switch (reversível)
        self.learning_mode = "LIMITED"  # LIMITED | OFF

        # limites de segurança (NUNCA passa disso)
        self.cooldown_min_factor = 0.8
        self.cooldown_max_factor = 1.5

        # estado adaptativo por par
        self.pair_adaptive_state = {}

        # =========================================================
        # ALO — LEARNING OBSERVER
        # =========================================================
        self.alo = alo

        self.notifier = TelegramNotifier(
            token="8696491310:AAF1czFwV394JaF4ur8sYxnUIlk5Irh3hWs",
            chat_id="7975792456",
        )

    # ========================================================
    # POSIÇÕES ATIVAS / CONTEXTO DINÂMICO
    # ========================================================

    def get_active_positions(self):
        return sum(1 for slot in self._slots.values() if slot.state == "RUNNING")

    def get_system_loss_streak(self) -> int:
        streak = 0

        for trade in reversed(self.trade_history):
            profit = float(trade.get("profit", 0.0))
            if profit < 0:
                streak += 1
            else:
                break

        return streak

    def get_recent_win_rate(self, window: int = 20) -> float:
        if not self.trade_history:
            return 0.50

        recent = self.trade_history[-window:]
        if not recent:
            return 0.50

        wins = sum(1 for trade in recent if float(trade.get("profit", 0.0)) > 0)
        return wins / len(recent)

    def get_drawdown_pct(self) -> float:
        current_balance = float(self.balance or 0.0)

        if current_balance > 0:
            if self.peak_balance <= 0:
                self.peak_balance = current_balance
            else:
                self.peak_balance = max(self.peak_balance, current_balance)

        if self.peak_balance <= 0:
            return 0.0

        drawdown = self.peak_balance - current_balance
        if drawdown <= 0:
            return 0.0

        return drawdown / self.peak_balance

    # ========================================================
    # HELPERS
    # ========================================================

    def _slot_has_live_position(self, slot) -> bool:
        if not self.position_manager or not slot.pair:
            return False
        return self.position_manager.has_position(symbol=slot.pair)

    def _sync_slot_from_position(self, slot):
        if not self.position_manager or not slot.pair:
            return

        pos = self.position_manager.get_position(symbol=slot.pair)
        if not pos:
            return

        slot.entry_price = pos.entry_price
        slot.quantity = pos.quantity

    def _now_ts(self):
        return time.time()

    def _normalize_symbol(self, symbol: str) -> str:
        return str(symbol).strip().upper()

    # ========================================================
    # H&A LEARNING SYNC
    # ========================================================

    def _sync_learning_context(self):
        """
        Sincroniza a memória operacional aprendida no PositionManager
        com o Radar e o DecisionEngine.

        Objetivo:
        - propagar penalty_map
        - propagar last_traded_symbol
        - manter o sistema adaptativo sem alterar a lógica existente
        """
        if not self.position_manager:
            return

        try:
            penalty_map = self.position_manager.get_penalty_map()
        except Exception:
            penalty_map = {}

        try:
            last_symbol = self.position_manager.get_last_traded_symbol()
        except Exception:
            last_symbol = None

        # -----------------------------
        # RADAR
        # -----------------------------
        if self.market_radar:
            try:
                if hasattr(self.market_radar, "set_penalty_map"):
                    self.market_radar.set_penalty_map(penalty_map)
            except Exception as e:
                print(f"[LEARNING SYNC] radar penalty sync error: {e}")

            try:
                if hasattr(self.market_radar, "set_last_traded_symbol"):
                    self.market_radar.set_last_traded_symbol(last_symbol)
            except Exception as e:
                print(f"[LEARNING SYNC] radar last symbol sync error: {e}")

        # -----------------------------
        # DECISION ENGINE
        # -----------------------------
        if self._decision_engine:
            try:
                self._decision_engine.penalty_map = penalty_map
            except Exception as e:
                print(f"[LEARNING SYNC] engine penalty sync error: {e}")

            try:
                self._decision_engine.last_traded_symbol = last_symbol
            except Exception as e:
                print(f"[LEARNING SYNC] engine last symbol sync error: {e}")

    # ========================================================
    # COOLDOWN POR LOSS REAL
    # ========================================================

    def _get_cooldown_seconds_for_pair(self, symbol: str) -> int:
        streak = self.pair_loss_streak.get(symbol, 0)

        if streak <= 1:
            return self.cooldown_loss_1
        elif streak == 2:
            return self.cooldown_loss_2
        else:
            return self.cooldown_loss_3

    def _apply_adaptive_cooldown(self, symbol: str, base_cooldown: int) -> int:
        """
        Ajuste adaptativo CONTROLADO do cooldown.
        - automático
        - limitado
        - auditável
        - reversível
        """
        symbol = self._normalize_symbol(symbol)

        if not self.learning_enabled or self.learning_mode != "LIMITED":
            return base_cooldown

        state = self.pair_adaptive_state.get(
            symbol,
            {
                "factor": 1.0,
                "wins": 0,
                "losses": 0,
            },
        )

        factor = float(state.get("factor", 1.0))

        # clamp de segurança
        factor = max(self.cooldown_min_factor, min(self.cooldown_max_factor, factor))

        adjusted = int(base_cooldown * factor)

        print(
            f"[ADAPTIVE COOLDOWN] {symbol} | "
            f"base={base_cooldown}s | "
            f"factor={factor:.2f} | "
            f"final={adjusted}s"
        )

        return adjusted

    def _refresh_loss_streak_if_expired(self, symbol: str):
        symbol = self._normalize_symbol(symbol)

        last_loss_at = self.pair_last_loss_at.get(symbol)
        if last_loss_at is None:
            return

        now = self._now_ts()
        elapsed = now - last_loss_at

        if elapsed >= self.loss_streak_reset_window:
            self.pair_loss_streak.pop(symbol, None)
            self.pair_last_loss_at.pop(symbol, None)
            print(f"[COOLDOWN] {symbol} streak resetado por janela expirada")

    def _register_loss_cooldown(self, symbol: str):
        symbol = self._normalize_symbol(symbol)

        self._refresh_loss_streak_if_expired(symbol)

        streak = self.pair_loss_streak.get(symbol, 0) + 1
        self.pair_loss_streak[symbol] = streak
        self.pair_last_loss_at[symbol] = self._now_ts()

        base_cooldown = self._get_cooldown_seconds_for_pair(symbol)
        cooldown_seconds = self._apply_adaptive_cooldown(symbol, base_cooldown)
        release_ts = self._now_ts() + cooldown_seconds
        self.pair_cooldowns[symbol] = release_ts

        print(
            f"[COOLDOWN] {symbol} BLOQUEADO | "
            f"loss_streak={streak} | "
            f"cooldown={cooldown_seconds}s | "
        )

        # ==========================================
        # LEARNING — LOSS
        # ==========================================
        if self.learning_enabled:
            state = self.pair_adaptive_state.get(
                symbol,
                {
                    "factor": 1.0,
                    "wins": 0,
                    "losses": 0,
                },
            )

            state["losses"] += 1

            # aumenta proteção
            state["factor"] *= 1.10

            self.pair_adaptive_state[symbol] = state

            print(
                f"[LEARNING] {symbol} ajustado após LOSS | factor={state['factor']:.2f}"
            )

    def _register_win_recovery(self, symbol: str):
        symbol = self._normalize_symbol(symbol)

        current_streak = self.pair_loss_streak.get(symbol, 0)

        if current_streak > 0:
            new_streak = current_streak - 1

            if new_streak <= 0:
                self.pair_loss_streak.pop(symbol, None)
                self.pair_last_loss_at.pop(symbol, None)
            else:
                self.pair_loss_streak[symbol] = new_streak

            print(
                f"[COOLDOWN] {symbol} RECUPERAÇÃO POR WIN | "
                f"loss_streak={self.pair_loss_streak.get(symbol, 0)}"
            )

        base_cooldown = self.cooldown_win
        cooldown_seconds = self._apply_adaptive_cooldown(symbol, base_cooldown)
        release_ts = self._now_ts() + cooldown_seconds
        self.pair_cooldowns[symbol] = release_ts

        print(
            f"[COOLDOWN] {symbol} BLOQUEADO APÓS WIN | " f"cooldown={cooldown_seconds}s"
        )

        # ==========================================
        # LEARNING — WIN
        # ==========================================
        if self.learning_enabled:
            state = self.pair_adaptive_state.get(
                symbol,
                {
                    "factor": 1.0,
                    "wins": 0,
                    "losses": 0,
                },
            )

            state["wins"] += 1

            # reduz proteção
            state["factor"] *= 0.95

            self.pair_adaptive_state[symbol] = state

            print(
                f"[LEARNING] {symbol} ajustado após WIN | factor={state['factor']:.2f}"
            )

    def _register_dynamic_reentry_control(
        self,
        symbol: str,
        pnl_usdc: float,
        entry_price: float,
        exit_price: float,
        duration_seconds: float,
        reason=None,
    ):
        symbol = self._normalize_symbol(symbol)

        pnl_pct = 0.0
        try:
            if entry_price and float(entry_price) > 0:
                pnl_pct = (float(exit_price) - float(entry_price)) / float(entry_price)
        except Exception:
            pnl_pct = 0.0

        duration_seconds = max(0.0, float(duration_seconds or 0.0))

        # 1) STOP muito rápido = provável erro de timing / virada brusca
        if pnl_usdc < 0 and duration_seconds <= self.drc_fast_stop_seconds:
            release_ts = self._now_ts() + self.drc_fast_stop_cooldown
            self.pair_cooldowns[symbol] = release_ts

            print(
                f"[DRC] {symbol} FAST STOP | "
                f"duration={duration_seconds:.0f}s | "
                f"cooldown={self.drc_fast_stop_cooldown}s | "
                f"reason={reason}"
            )
            return

        # 2) STOP curto = bloqueio intermediário
        if pnl_usdc < 0 and duration_seconds <= self.drc_quick_stop_seconds:
            release_ts = self._now_ts() + self.drc_quick_stop_cooldown
            self.pair_cooldowns[symbol] = release_ts

            print(
                f"[DRC] {symbol} QUICK STOP | "
                f"duration={duration_seconds:.0f}s | "
                f"cooldown={self.drc_quick_stop_cooldown}s | "
                f"reason={reason}"
            )
            return

        # 3) lucro forte = exaustão, sem reentrada imediata
        if pnl_usdc > 0 and pnl_pct >= self.drc_exhaustion_profit_pct:
            release_ts = self._now_ts() + self.drc_exhaustion_cooldown
            self.pair_cooldowns[symbol] = release_ts

            print(
                f"[DRC] {symbol} EXAUSTÃO | "
                f"pnl_pct={pnl_pct*100:.2f}% | "
                f"duration={duration_seconds:.0f}s | "
                f"cooldown={self.drc_exhaustion_cooldown}s"
            )
            return

        # 4) lucro bom/saudável = cooldown menor, mas ainda protetivo
        if pnl_usdc > 0 and pnl_pct >= self.drc_good_profit_pct:
            release_ts = self._now_ts() + self.drc_good_profit_cooldown
            self.pair_cooldowns[symbol] = release_ts

            print(
                f"[DRC] {symbol} GOOD PROFIT | "
                f"pnl_pct={pnl_pct*100:.2f}% | "
                f"duration={duration_seconds:.0f}s | "
                f"cooldown={self.drc_good_profit_cooldown}s"
            )
            return

    def _is_pair_blocked(self, symbol: str) -> bool:
        symbol = self._normalize_symbol(symbol)

        self._refresh_loss_streak_if_expired(symbol)

        release_ts = self.pair_cooldowns.get(symbol)
        if release_ts is None:
            return False

        now = self._now_ts()

        if now >= release_ts:
            self.pair_cooldowns.pop(symbol, None)
            return False

        remaining = int(release_ts - now)
        print(f"[COOLDOWN] {symbol} ainda bloqueado por {remaining}s")
        return True

    # ========================================================
    # BLOQUEIO CURTO ENTRE CICLOS
    # ========================================================

    def _start_new_cycle(self):
        expired = []

        for symbol, remaining_cycles in list(self.rejected_symbols_cooldown.items()):
            new_value = remaining_cycles - 1

            if new_value <= 0:
                expired.append(symbol)
            else:
                self.rejected_symbols_cooldown[symbol] = new_value

        for symbol in expired:
            self.rejected_symbols_cooldown.pop(symbol, None)

        if self.rejected_symbols_cooldown:
            print(
                f"[REJECTION COOLDOWN] ativos bloqueados: {self.rejected_symbols_cooldown}"
            )

    def _block_rejected_symbol(self, symbol: str, cycles: int):
        symbol = self._normalize_symbol(symbol)

        current = self.rejected_symbols_cooldown.get(symbol, 0)
        self.rejected_symbols_cooldown[symbol] = max(current, cycles)

        print(
            f"[REJECTION COOLDOWN] {symbol} bloqueado por "
            f"{self.rejected_symbols_cooldown[symbol]} ciclo(s)"
        )

    def _unblock_rejected_symbol(self, symbol: str):
        symbol = self._normalize_symbol(symbol)

        if symbol in self.rejected_symbols_cooldown:
            self.rejected_symbols_cooldown.pop(symbol, None)
            print(f"[REJECTION COOLDOWN] {symbol} removido do bloqueio curto")

    def _is_rejected_symbol_blocked(self, symbol: str) -> bool:
        symbol = self._normalize_symbol(symbol)
        return self.rejected_symbols_cooldown.get(symbol, 0) > 0

    # ========================================================
    # MQII GATE
    # ========================================================

    def _mqii_blocks_new_entries(self) -> bool:
        """
        Gate institucional v1:
        - bloqueia novas entradas quando MQII estiver em NO_TRADE
        - não interrompe monitoramento nem SELL
        """
        if not self.market_radar:
            return False

        try:
            mqii = getattr(self.market_radar, "market_quality", None)

            if not mqii:
                return False

            state = str(mqii.get("state", "")).strip().upper()

            if state == "NO_TRADE":
                print(
                    "[MQII GATE] NOVAS ENTRADAS BLOQUEADAS | "
                    f"state={state} | "
                    f"label={mqii.get('label', '')} | "
                    f"score={mqii.get('score', 0.0)} | "
                    f"message={mqii.get('message', '')}"
                )
                return True

        except Exception as e:
            print(f"[MQII GATE ERROR] {e}")

        return False

    # ========================================================
    # MQII CAPITAL ADJUSTMENT
    # ========================================================

    def _mqii_capital_multiplier(self) -> float:
        if not self.market_radar:
            return 1.0

        try:
            mqii = getattr(self.market_radar, "market_quality", None)

            if not mqii:
                return 1.0

            state = str(mqii.get("state", "")).strip().upper()

            if state == "CAUTIOUS":
                return 0.5
            elif state == "TRADE_OK":
                return 1.0
            elif state == "AGGRESSIVE_OK":
                return 1.2

        except Exception as e:
            print(f"[MQII CAPITAL ERROR] {e}")

        return 1.0

    def _get_setup_quality_multiplier(self, signal, slot):

        try:
            # =========================
            # DADOS BASE
            # =========================
            rsi = float(getattr(signal, "rsi", 50.0))
            volume_ratio = float(getattr(signal, "volume_ratio", 1.0))
            price = float(getattr(signal, "entry_price", 0.0))
            ema_fast = float(getattr(signal, "ema_fast", 0.0))
            ema_slow = float(getattr(signal, "ema_slow", 0.0))

            # =========================
            # PROTEÇÃO BASE
            # =========================
            if price <= 0 or ema_fast <= 0 or ema_slow <= 0:
                return 1.0

            # =========================
            # FORÇA DE TENDÊNCIA (SPREAD)
            # =========================
            spread = (ema_fast - ema_slow) / ema_slow if ema_slow > 0 else 0.0

            # =========================
            # CLASSIFICAÇÃO
            # =========================

            # MUITO FORTE
            if spread > 0.004 and volume_ratio >= 2.0 and 50 <= rsi <= 65:
                return 1.20

            # FORTE
            if spread > 0.0025 and volume_ratio >= 1.5 and 48 <= rsi <= 68:
                return 1.10

            # RUIM (entrada fraca)
            if spread < 0.0015 or volume_ratio < 1.0 or rsi > 72 or rsi < 40:
                return 0.80

            # NORMAL
            return 1.00

        except Exception as e:
            print(f"[QUALITY MULTIPLIER ERROR] {e}")
            return 1.0

    # ========================================================
    # SNAPSHOT
    # ========================================================

    def _build_snapshot_from_opportunity(self, opportunity):
        symbol = self._normalize_symbol(opportunity.get("symbol", ""))

        snapshot_obj = opportunity.get("snapshot")
        if not symbol or snapshot_obj is None:
            return None

        try:
            price_data = self.client.get_symbol_ticker(symbol=symbol)
            current_price = float(price_data["price"])
        except Exception as e:
            print(f"[SLOT] erro ao buscar preço atual de {symbol}: {e}")
            return None

        atr = 0.001
        if current_price > 0:
            atr = current_price * 0.003

        return MarketSnapshot(
            pair=symbol,
            price=current_price,
            rsi=float(getattr(snapshot_obj, "rsi_14", 0.0)),
            ema_fast=float(getattr(snapshot_obj, "ema_10", 0.0)),
            ema_slow=float(getattr(snapshot_obj, "ema_20", 0.0)),
            volume_ratio=float(getattr(snapshot_obj, "volume_ratio", 0.0)),
            atr=float(atr),
        )

    # ========================================================
    # SELEÇÃO DE OPORTUNIDADE
    # ========================================================

    def _pick_opportunity_for_slot(
        self, opportunities, pairs_in_use, attempted_symbols
    ):
        """
        Seleciona UMA oportunidade por slot por ciclo.
        Não repete símbolo já tentado no mesmo ciclo.
        Respeita cooldown por loss real.
        Respeita bloqueio curto pós-rejeição.
        """
        if not opportunities:
            return None, None

        for opportunity in opportunities:
            symbol = opportunity.get("symbol")

            if not symbol:
                continue

            symbol = self._normalize_symbol(symbol)

            if symbol in pairs_in_use:
                continue

            if symbol in attempted_symbols:
                continue

            if self._is_pair_blocked(symbol):
                attempted_symbols.add(symbol)
                continue

            if self._is_rejected_symbol_blocked(symbol):
                print(f"[PICK BLOCK] {symbol} bloqueado por rejection cooldown")
                attempted_symbols.add(symbol)
                continue

            attempted_symbols.add(symbol)
            return opportunity, symbol

        return None, None

    # ========================================================
    # CICLO PRINCIPAL
    # ========================================================

    def run_cycle(self):

        # ==========================================================
        # 1. SYNC + CONTEXTO GLOBAL
        # ==========================================================
        self._sync_learning_context()

        try:
            self.balance = float(self.executor.get_balance("USDC"))

            if self.boot_balance <= 0:
                self.boot_balance = self.balance

            if self.peak_balance <= 0:
                self.peak_balance = self.balance
            else:
                self.peak_balance = max(self.peak_balance, self.balance)

            print(f"[BALANCE REAL EXECUTOR] {self.balance:.4f}")

        except Exception as e:
            print(f"[BALANCE ERROR] {e}")

        self._cycle_counter += 1
        self._start_new_cycle()

        # ==========================================================
        # 2. SCAN GLOBAL (1x POR CICLO)
        # ==========================================================
        opportunities = []

        if self.market_radar:
            radar_data = self.market_radar.get_top(10)
            if radar_data:
                opportunities = radar_data

        print("OPPORTUNITIES:", opportunities[:3])

        self.last_opportunities = opportunities

        # ==========================================================
        # 2.1 MQII GATE (BLOQUEIO DE NOVAS ENTRADAS)
        # ==========================================================
        mqii_blocks_entries = self._mqii_blocks_new_entries()

        # ==========================================================
        # 3. CONTEXTO GLOBAL DE BLOQUEIO
        # ==========================================================
        pairs_in_use = {
            self._normalize_symbol(slot.pair)
            for slot in self._slots.values()
            if slot.pair and slot.state in ("ANALYZING", "READY", "RUNNING")
        }

        attempted_symbols = set()
        approved_candidates = []

        print(
            "[SLOT DEBUG] slots:",
            {sid: slot.state for sid, slot in self._slots.items()},
        )
        print("[SLOT DEBUG] approved_candidates:", approved_candidates)

        # ==========================================================
        # 2.1 MQII GATE
        # ==========================================================
        if mqii_blocks_entries:
            print("[MQII GATE] Pré-seleção global ignorada neste ciclo")

        # ==========================================================
        # 4. PRÉ-SELEÇÃO GLOBAL (ANTI-REENTRADA)
        # ==========================================================
        if not mqii_blocks_entries:
            for opportunity in opportunities:

                symbol = opportunity.get("symbol")
                if not symbol:
                    continue

                symbol = self._normalize_symbol(symbol)

                # 🚨 BLOQUEIO FORTE IMEDIATO (ANTES DE QUALQUER COISA)
                if self._is_pair_blocked(symbol):
                    print(f"[GLOBAL BLOCK] {symbol} bloqueado por cooldown (LOSS)")
                    continue

                if symbol in pairs_in_use:
                    continue

                if symbol in attempted_symbols:
                    continue

                snapshot = self._build_snapshot_from_opportunity(opportunity)

                if snapshot is None:
                    continue

                signal = None

                if self._decision_engine:
                    signal = self._decision_engine.evaluate_buy(snapshot)

                if not signal:
                    print(
                        f"[DECISION REJECTION] {symbol} | "
                        f"snapshot_price={snapshot.price:.8f} | "
                        f"rsi={snapshot.rsi:.2f} | "
                        f"ema_fast={snapshot.ema_fast:.8f} | "
                        f"ema_slow={snapshot.ema_slow:.8f} | "
                        f"volume_ratio={snapshot.volume_ratio:.4f} | "
                        f"atr={snapshot.atr:.8f}"
                    )

                # ==========================================================
                # ALO GATE v1 (ALO + MQII CONSENSO)
                # ==========================================================
                # ==========================================================
                try:
                    if signal:

                        from core.alo import AloVisionEngine

                        if not hasattr(self, "_alo_vision"):
                            self._alo_vision = AloVisionEngine()

                        # usa snapshot já existente
                        vision = self._alo_vision.analyze(
                            snapshot=snapshot,
                            liquidity_data=getattr(
                                self.market_radar, "market_liquidity", None
                            ),
                        )

                        # ======================================================
                        # PROTEÇÃO — VISÃO INVÁLIDA
                        # ======================================================
                        if (
                            not vision
                            or not hasattr(vision, "inference")
                            or not vision.inference
                        ):
                            print(f"[ALO GATE] visão inválida para {symbol}")
                            signal = None
                            self._block_rejected_symbol(symbol, cycles=1)
                            continue

                        guide = vision.inference.guidance
                        confidence = vision.inference.confidence_label

                        # ======================================================
                        # ALO GATE — BLOQUEIO POR BAIXA CONFIANÇA
                        # ======================================================
                        selection_score = 0.0
                        try:
                            selection_score = float(
                                opportunity.get("selection_score", 0.0)
                            )
                        except Exception:
                            selection_score = 0.0

                        is_premium_setup = (
                            selection_score >= 0.90
                            and float(snapshot.price) > 0
                            and float(snapshot.ema_fast) > float(snapshot.ema_slow) > 0
                            and float(snapshot.volume_ratio) >= 1.25
                            and 45 <= float(snapshot.rsi) <= 68
                        )

                        if confidence == "MUITO_BAIXA":
                            if not is_premium_setup:
                                print(
                                    f"[ALO GATE] BLOQUEADO {symbol} | "
                                    f"motivo=BAIXA_CONFIANCA | conf={confidence}"
                                )

                                self._block_rejected_symbol(symbol, cycles=1)
                                signal = None
                            else:
                                print(
                                    f"[ALO GATE] LIBERAÇÃO CONTROLADA {symbol} | "
                                    f"motivo=SETUP_PREMIUM | conf={confidence} | "
                                    f"selection_score={selection_score:.4f}"
                                )

                        # MQII state (macro)
                        mqii_state = ""
                        try:
                            if self.market_radar:
                                mqii = getattr(
                                    self.market_radar, "market_quality", None
                                )
                                if mqii:
                                    mqii_state = (
                                        str(mqii.get("state", "")).strip().upper()
                                    )
                        except Exception:
                            pass

                        # ======================================================
                        # REGRA DE BLOQUEIO (CONSENSO)
                        # ======================================================
                        if (
                            guide in ("EVITAR", "INVALIDAR")
                            and mqii_state == "NO_TRADE"
                        ):

                            print(
                                f"[ALO GATE] BLOQUEADO NO CICLO {symbol} | "
                                f"guide={guide} | conf={confidence} | mqii={mqii_state}"
                            )

                            signal = None

                except Exception as e:
                    print(f"[ALO GATE ERROR] {e}")
                    signal = None
                    self._block_rejected_symbol(symbol, cycles=1)

                # ==========================================================
                # BLOQUEIOS APÓS VALIDAÇÃO (ICfactory)
                # ==========================================================
                if signal:
                    if self._is_pair_blocked(symbol):
                        print(f"[POST-CHECK BLOCK] {symbol} bloqueado por cooldown")
                        signal = None

                    elif self._is_rejected_symbol_blocked(symbol):
                        print(
                            f"[POST-CHECK BLOCK] {symbol} bloqueado por rejection cooldown"
                        )
                        signal = None

                # ==========================================================
                # ALO INTELIGENTE GATE v1 (INFLUÊNCIA LEVE)
                # ==========================================================
                if signal:
                    try:
                        from core.alo_intelligence.alo_core import ALOIntelligentCore
                        from core.alo_intelligence.alo_models import (
                            ALOMode,
                            TechnicalContext,
                            MacroMarketContext,
                            MemoryContext,
                            GuidanceType,
                        )

                        if not hasattr(self, "_alo_intelligent"):
                            self._alo_intelligent = ALOIntelligentCore(
                                mode=ALOMode.ADVISORY
                            )

                        snapshot_obj = opportunity.get("snapshot")
                        analysis_data = opportunity.get("analysis", {}) or {}
                        market_context_data = (
                            opportunity.get("market_context", {}) or {}
                        )

                        technical = TechnicalContext(
                            price=float(getattr(snapshot_obj, "price", 0.0)),
                            rsi=float(getattr(snapshot_obj, "rsi_14", 50.0)),
                            ema_fast=float(getattr(snapshot_obj, "ema_10", 0.0)),
                            ema_slow=float(getattr(snapshot_obj, "ema_20", 0.0)),
                            ema_trend=float(getattr(snapshot_obj, "ema_50", 0.0)),
                            volume_ratio=float(
                                getattr(snapshot_obj, "volume_ratio", 1.0)
                            ),
                            trend=str(analysis_data.get("trend", "")),
                            momentum=str(analysis_data.get("momentum", "")),
                            market_state=str(analysis_data.get("market_state", "")),
                            selection_score=float(
                                opportunity.get("selection_score", 0.0)
                            ),
                            market_score=float(opportunity.get("score", 0.0)),
                            base_score=float(opportunity.get("base_score", 0.0)),
                            penalty=float(opportunity.get("penalty", 0.0)),
                        )

                        macro = MacroMarketContext(
                            liquidity_score=float(
                                getattr(
                                    getattr(self.market_radar, "market_liquidity", {})
                                    or {},
                                    "get",
                                    lambda *_: 0.5,
                                )("liquidity_score", 0.5)
                            ),
                            liquidity_label=str(
                                getattr(
                                    getattr(self.market_radar, "market_liquidity", {})
                                    or {},
                                    "get",
                                    lambda *_: "UNKNOWN",
                                )("liquidity_label", "UNKNOWN")
                            ),
                            liquidity_message=str(
                                getattr(
                                    getattr(self.market_radar, "market_liquidity", {})
                                    or {},
                                    "get",
                                    lambda *_: "",
                                )("liquidity_message", "")
                            ),
                            avg_volume_ratio=float(
                                market_context_data.get("avg_volume_ratio", 1.0)
                            ),
                            uptrend_count=int(
                                market_context_data.get("uptrend_count", 0)
                            ),
                            refined_count=int(
                                market_context_data.get("refined_count", 0)
                            ),
                            approved_count=int(
                                market_context_data.get("approved_count", 0)
                            ),
                            total_assets=int(
                                market_context_data.get("total_assets", 40)
                            ),
                            market_regime_internal=str(
                                getattr(
                                    getattr(self.market_radar, "market_quality", {})
                                    or {},
                                    "get",
                                    lambda *_: "",
                                )("state", "")
                            ),
                        )

                        drc_data = {}

                        try:
                            if (
                                hasattr(self, "position_manager")
                                and self.position_manager
                            ):
                                drc_data = getattr(
                                    self.position_manager, "drc_memory", {}
                                ).get(symbol, {})
                        except Exception:
                            drc_data = {}

                        memory = MemoryContext(
                            same_symbol_recent_trades=int(
                                drc_data.get("recent_trades", 0) or 0
                            ),
                            same_symbol_recent_failures=int(
                                drc_data.get("recent_failures", 0) or 0
                            ),
                        )

                        guidance = self._alo_intelligent.evaluate(
                            symbol=symbol,
                            technical=technical,
                            macro=macro,
                            memory=memory,
                        )

                        print(f"[ALO INTEL GATE] {guidance.explainability_text}")

                        if guidance.guidance in (
                            GuidanceType.HARD_BLOCK,
                            GuidanceType.TEMPORARY_BLOCK,
                        ):
                            print(
                                f"[ALO INTEL GATE] BLOQUEADO {symbol} | "
                                f"guidance={guidance.guidance.value}"
                            )
                            signal = None
                            self._block_rejected_symbol(symbol, cycles=2)

                        elif (
                            guidance.guidance
                            == GuidanceType.REQUIRE_STRONGER_CONFIRMATION
                        ):
                            selection_score = float(
                                opportunity.get("selection_score", 0.0)
                            )

                            if selection_score < 0.85:
                                print(
                                    f"[ALO INTEL GATE] CONFIRMAÇÃO INSUFICIENTE {symbol} | "
                                    f"guidance={guidance.guidance.value} | "
                                    f"selection_score={selection_score:.4f}"
                                )
                                signal = None
                                self._block_rejected_symbol(symbol, cycles=1)

                    except Exception as e:
                        print(f"[ALO INTEL GATE ERROR] {symbol} | erro={e}")

                    attempted_symbols.add(symbol)

                if signal:
                    print(f"[SLOT DEBUG] CANDIDATO APROVADO: {symbol}")
                    approved_candidates.append((symbol, signal))
                else:

                    try:
                        if self.lc1_adapter and hasattr(
                            self.lc1_adapter, "build_event"
                        ):

                            analysis_data = (
                                opportunity.get("analysis", {})
                                if isinstance(opportunity, dict)
                                else {}
                            )

                            snapshot_obj = (
                                opportunity.get("snapshot")
                                if isinstance(opportunity, dict)
                                else None
                            )

                            market_liquidity = (
                                getattr(self.market_radar, "market_liquidity", {}) or {}
                            )

                            event = self.lc1_adapter.build_event(
                                symbol=symbol,
                                reason="ENGINE_REJECTION",
                                analysis={
                                    **analysis_data,
                                    "selection_score": (
                                        opportunity.get("selection_score", 0.0)
                                        if isinstance(opportunity, dict)
                                        else 0.0
                                    ),
                                    "base_score": (
                                        opportunity.get("base_score", 0.0)
                                        if isinstance(opportunity, dict)
                                        else 0.0
                                    ),
                                    "score": (
                                        opportunity.get("score", 0.0)
                                        if isinstance(opportunity, dict)
                                        else 0.0
                                    ),
                                    "penalty": (
                                        opportunity.get("penalty", 0)
                                        if isinstance(opportunity, dict)
                                        else 0
                                    ),
                                },
                                snapshot={
                                    "price": float(getattr(snapshot_obj, "price", 0.0)),
                                    "ema_10": float(
                                        getattr(snapshot_obj, "ema_10", 0.0)
                                    ),
                                    "ema_20": float(
                                        getattr(snapshot_obj, "ema_20", 0.0)
                                    ),
                                    "ema_50": float(
                                        getattr(snapshot_obj, "ema_50", 0.0)
                                    ),
                                    "rsi_14": float(
                                        getattr(snapshot_obj, "rsi_14", 0.0)
                                    ),
                                    "volume_ratio": float(
                                        getattr(snapshot_obj, "volume_ratio", 0.0)
                                    ),
                                },
                                market_context={
                                    "reason": "BUY_SIGNAL_FALSE",
                                    "stage": "PRE_SELECTION",
                                    "mqii_state": str(
                                        getattr(
                                            getattr(
                                                self.market_radar, "market_quality", {}
                                            ),
                                            "get",
                                            lambda *_: "",
                                        )("state", "")
                                    )
                                    .strip()
                                    .upper(),
                                    "mqii_label": getattr(
                                        self.market_radar, "market_quality", {}
                                    ).get("label", ""),
                                    "mqii_score": float(
                                        getattr(
                                            self.market_radar, "market_quality", {}
                                        ).get("score", 0.0)
                                    ),
                                    "liquidity_score": float(
                                        market_liquidity.get("liquidity_score", 0.0)
                                    ),
                                    "liquidity_label": market_liquidity.get(
                                        "liquidity_label", ""
                                    ),
                                    "avg_volume_ratio": float(
                                        market_liquidity.get("avg_volume_ratio", 0.0)
                                    ),
                                    "uptrend_count": int(
                                        market_liquidity.get("uptrend_count", 0)
                                    ),
                                    "refined_count": int(
                                        market_liquidity.get("refined_count", 0)
                                    ),
                                    "approved_count": int(
                                        market_liquidity.get("approved_count", 0)
                                    ),
                                },
                                event_type="NON_EXECUTION",
                                source="slot_controller",
                                summary="ENGINE_BLOCKED_ENTRY",
                            )

                            self.lc1_adapter.record_event(event)
                            if hasattr(self, "alo") and self.alo:
                                try:
                                    self.alo.ingest_event(event)
                                except Exception as e:
                                    print(f"[ALO INGEST ERROR] {e}")

                    except Exception as e:
                        print(f"[LC1E ENGINE ERROR] {symbol} | erro={e}")

        # ==========================================================
        # 5. EXECUÇÃO CONTROLADA POR SLOT
        # ==========================================================
        candidate_index = 0

        buy_executed_in_cycle = False

        for slot in self._slots.values():

            previous_state = slot.state

            # -------------------------------
            # SLOT LIVRE → ENTRADA
            # -------------------------------
            if slot.state == "IDLE":

                if buy_executed_in_cycle:
                    continue

                if candidate_index >= len(approved_candidates):
                    continue

                symbol, signal = approved_candidates[candidate_index]

                slot.pair = symbol
                slot.pending_buy_signal = signal
                slot.start_analysis()
                pairs_in_use.add(symbol)
                self._unblock_rejected_symbol(symbol)

                print(f"[SLOT {slot.slot_id}] BUY APROVADO (GLOBAL): {symbol}")

                buy_executed_in_cycle = True

                candidate_index += 1
            # -------------------------------
            # PROCESSAMENTO NORMAL
            # -------------------------------
            else:
                was_ready = slot.state == "READY"

                slot.tick()

                if was_ready and slot.state == "RUNNING":
                    self._execute_buy(slot)

            # -------------------------------
            # SYNC POSIÇÃO
            # -------------------------------
            if slot.state == "RUNNING":
                self._sync_slot_from_position(slot)

            # ======================================================
            # 6. MONITORAMENTO (SELL CENTRAL)
            # ======================================================
            if slot.state == "RUNNING":

                try:
                    price_data = self.client.get_symbol_ticker(symbol=slot.pair)
                    current_price = float(price_data["price"])

                    try:
                        depth = self.client.get_order_book(symbol=slot.pair, limit=5)
                        if depth and depth.get("bids"):
                            current_price = float(depth["bids"][0][0])
                    except Exception:
                        pass

                    entry_price = slot.entry_price

                    if entry_price is None or entry_price <= 0:
                        if not self._slot_has_live_position(slot):
                            print(f"[SLOT {slot.slot_id}] ENTRY PRICE INVÁLIDO → RESET")
                            slot.reset()
                            continue
                        else:
                            continue

                    pnl = (current_price - entry_price) / entry_price

                    print(
                        f"[MONITOR] slot={slot.slot_id} {slot.pair} "
                        f"price={current_price:.6f} pnl={pnl*100:.3f}%"
                    )

                    if self.position_manager and slot.pair:
                        pos = self.position_manager.get_position(symbol=slot.pair)

                        if pos:
                            reason = self.position_manager.update_price(
                                symbol=slot.pair, price=current_price
                            )

                            if reason is not None:
                                print(
                                    f"[SLOT {slot.slot_id}] SELL via PositionManager → {reason}"
                                )
                                self._execute_sell(slot, reason)

                except Exception as e:
                    print(f"[SLOT {slot.slot_id}] MONITOR ERROR: {e}")

            # ======================================================
            # 7. FINALIZAÇÃO
            # ======================================================
            if previous_state == "RUNNING" and slot.state == "DONE":
                slot.reset()

            if slot.state == "RUNNING" and slot.pair:
                if self.position_manager and not self.position_manager.has_position(
                    symbol=slot.pair
                ):
                    if slot.entry_price and slot.entry_price > 0:
                        slot._state = "DONE"

    # ========================================================
    # EXECUÇÃO BUY
    # ========================================================

    def _execute_buy(self, slot):

        try:
            if not self.client or not self.executor:
                print(f"[SLOT {slot.slot_id}] BUY: executor/client não definido")
                slot.reset()
                return

            if not slot.pair:
                print(f"[SLOT {slot.slot_id}] BUY: pair inválido")
                slot.reset()
                return

            signal = getattr(slot, "pending_buy_signal", None)
            if signal is None:
                print(f"[SLOT {slot.slot_id}] BUY: sinal pendente ausente")
                slot.reset()
                return

            # ========================================================
            # MQII CAPITAL AJUSTE
            # ========================================================
            mqii_multiplier = self._mqii_capital_multiplier()
            quality_multiplier = self._get_setup_quality_multiplier(signal, slot)

            raw_multiplier = mqii_multiplier * quality_multiplier

            # ========================================================
            # POSITION SIZING DINÂMICO LIGHT
            # ========================================================
            # Regra conservadora:
            # - nunca aumenta acima do capital base
            # - reduz em mercado/qualidade fraca
            # - preserva setup forte com capital cheio

            multiplier = max(0.50, min(raw_multiplier, 1.00))

            original_capital = signal.allocated_usdc
            adjusted_capital = original_capital * multiplier

            signal.allocated_usdc = adjusted_capital

            print(
                f"[MQII CAPITAL] multiplier={multiplier} | "
                f"original={original_capital:.4f} | "
                f"adjusted={adjusted_capital:.4f}"
            )

            slot.pair = self._normalize_symbol(slot.pair)

            # ========================================================
            # REVALIDAÇÃO FINAL ANTI-REENTRADA / ANTI-RACE CONDITION
            # ========================================================
            if self._is_pair_blocked(slot.pair):
                print(
                    f"[SLOT {slot.slot_id}] BUY CANCELADO NO GATE FINAL: "
                    f"{slot.pair} bloqueado por cooldown"
                )
                self._block_rejected_symbol(slot.pair, cycles=1)
                slot.pending_buy_signal = None
                slot.reset()
                return

            if self._is_rejected_symbol_blocked(slot.pair):
                print(
                    f"[SLOT {slot.slot_id}] BUY CANCELADO NO GATE FINAL: "
                    f"{slot.pair} bloqueado por rejection cooldown"
                )
                slot.pending_buy_signal = None
                slot.reset()
                return

            print(
                f"[SLOT {slot.slot_id}] EXECUTING BUY {signal.pair} "
                f"capital={signal.allocated_usdc:.4f} price={signal.entry_price:.8f}"
            )

            result = self.executor.execute_buy(signal)

            print(f"[SLOT {slot.slot_id}] BUY RESULT: {result}")

            if not result:
                self._block_rejected_symbol(slot.pair, cycles=1)
                print(f"[SLOT {slot.slot_id}] BUY FALHOU NA EXECUÇÃO: {slot.pair}")

                # ==========================================
                # LC1E — EXECUTION FAILURE
                # ==========================================
                try:
                    if self.lc1_adapter and hasattr(self.lc1_adapter, "build_event"):
                        event = self.lc1_adapter.build_event(
                            symbol=slot.pair,
                            reason="EXECUTION_FAILED",
                            analysis={
                                "source": "executor",
                                "slot_id": slot.slot_id,
                            },
                            snapshot=None,
                            market_context={
                                "slot_id": slot.slot_id,
                                "stage": "EXECUTION",
                            },
                            event_type="NON_EXECUTION",
                            source="slot_controller",
                            summary="BUY_FAILED_EXECUTION",
                        )
                        self.lc1_adapter.record_event(event)
                        if hasattr(self, "alo") and self.alo:
                            try:
                                self.alo.ingest_event(event)
                            except Exception as e:
                                print(f"[ALO INGEST ERROR] {e}")
                except Exception as e:
                    print(f"[LC1E EXECUTION ERROR] {slot.pair} | erro={e}")

                slot.pending_buy_signal = None
                slot.reset()
                return

            slot.entry_price = result.entry_price
            slot.quantity = result.quantity
            slot.pending_buy_signal = None
            slot._state = "RUNNING"
            self._unblock_rejected_symbol(slot.pair)

            try:
                self.notifier.send(
                    f"🟢 BUY EXECUTADO\n"
                    f"Par: {slot.pair}\n"
                    f"Entrada: {result.entry_price:.8f}\n"
                    f"Qtd: {result.quantity:.8f}"
                )
            except Exception as e:
                print(f"[TELEGRAM BUY ERROR] {e}")

        except Exception as e:
            print(f"[SLOT {slot.slot_id}] BUY ERROR: {e}")
            if slot.pair:
                self._block_rejected_symbol(slot.pair, cycles=3)
            slot.pending_buy_signal = None
            slot.reset()

    # ========================================================
    # EXECUÇÃO SELL
    # ========================================================

    def _execute_sell(self, slot, reason=CloseReason.MANUAL):

        try:
            if not self.executor or not self.client:
                print(f"[SLOT {slot.slot_id}] SELL: executor/client não definido")
                return

            if not slot.pair:
                print(f"[SLOT {slot.slot_id}] SELL: pair inválido")
                return

            slot.pair = self._normalize_symbol(slot.pair)

            print(f"[SLOT {slot.slot_id}] EXECUTING SELL {slot.pair}")

            result = self.executor.execute_sell(slot.pair, reason)

            print(f"[SLOT {slot.slot_id}] SELL RESULT: {result}")

            if not result:
                print(f"[SLOT {slot.slot_id}] SELL FAILED")
                return

            # =====================================================
            # 🔥 SINCRONIZA COM POSITION MANAGER (OBRIGATÓRIO)
            # =====================================================
            if self.position_manager:
                try:
                    self.position_manager.close_position(
                        symbol=slot.pair,
                        exit_price=result.exit_price,
                        reason=reason,
                    )
                except Exception as e:
                    print(f"[POSITION MANAGER CLOSE ERROR] {slot.pair} | erro={e}")

            exit_ts = time.time()
            entry_ts = 0.0

            try:
                if self.position_manager:
                    pos = self.position_manager.get_position(symbol=slot.pair)
                    if pos and hasattr(pos, "opened_at") and pos.opened_at:
                        entry_ts = float(pos.opened_at)
            except Exception:
                entry_ts = 0.0

            duration_seconds = max(0.0, exit_ts - entry_ts) if entry_ts > 0 else 0.0

            trade = {
                "pair": result.pair,
                "entry": result.entry_price,
                "exit": result.exit_price,
                "qty": result.quantity,
                "profit": result.net_pnl_usdc,
                "reason": str(reason),
                "ts": exit_ts,
                "duration_seconds": duration_seconds,
            }

            self.trade_history.append(trade)

            if len(self.trade_history) > 50:
                self.trade_history.pop(0)

            self.profit_today += result.net_pnl_usdc
            self.profit_total += result.net_pnl_usdc

            try:
                self.balance = float(self.executor.get_balance("USDC"))
                self.peak_balance = max(self.peak_balance, self.balance)
            except Exception:
                pass

            if result.net_pnl_usdc < 0:
                self._register_loss_cooldown(result.pair)

                # =====================================================
                # QUARENTENA EXTRA PÓS-STAGNATION
                # Evita reciclagem precoce do mesmo par em mercado morno
                # =====================================================
                try:
                    if reason == CloseReason.DYNAMIC_STAGNATION:
                        self._block_rejected_symbol(result.pair, cycles=15)
                        print(
                            f"[STAGNATION QUARANTINE] {result.pair} bloqueado por "
                            f"{self.rejected_symbols_cooldown.get(self._normalize_symbol(result.pair), 0)} ciclo(s)"
                        )
                except Exception as e:
                    print(f"[STAGNATION QUARANTINE ERROR] {result.pair} | erro={e}")

            else:
                self._register_win_recovery(result.pair)

            self._register_dynamic_reentry_control(
                symbol=result.pair,
                pnl_usdc=result.net_pnl_usdc,
                entry_price=result.entry_price,
                exit_price=result.exit_price,
                duration_seconds=duration_seconds,
                reason=reason,
            )
            print(
                f"[TRADE] {result.pair} | "
                f"entry={result.entry_price:.6f} exit={result.exit_price:.6f} "
                f"profit={result.net_pnl_usdc:.4f} USDC"
            )

            try:
                emoji = "🟢" if result.net_pnl_usdc >= 0 else "🔴"
                self.notifier.send(
                    f"{emoji} SELL EXECUTADO\n"
                    f"Par: {result.pair}\n"
                    f"Entrada: {result.entry_price:.8f}\n"
                    f"Saída: {result.exit_price:.8f}\n"
                    f"Resultado: {result.net_pnl_usdc:.4f} USDC\n"
                    f"Motivo: {reason}"
                )
            except Exception as e:
                print(f"[TELEGRAM SELL ERROR] {e}")

            slot.pending_buy_signal = None
            slot._state = "DONE"

        except Exception as e:
            print(f"[SLOT {slot.slot_id}] SELL ERROR: {e}")

    # ========================================================
    # ACESSO
    # ========================================================

    def get_slots(self):
        return self._slots

    def get_slot(self, slot_id):
        return self._slots.get(slot_id)
