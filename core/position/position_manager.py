# ============================================================
# core/position/position_manager.py
# POSITION MANAGER — SAFE VERSION (COMPATÍVEL)
# + H&A LEARNING CORE
# + LUCRO DINÂMICO NÍVEL 2 (AGRESSIVO COM CONTROLES)
# ============================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from core.notifications.telegram_notifier import TelegramNotifier
from enum import Enum
from typing import Optional, Dict, List

from core.config.trading_config import *
from core.lc1.lc1_logger import LC1Logger

logger = logging.getLogger(__name__)


def get_pnl_emoji(pnl: float) -> str:
    if pnl > 0:
        return "🟢"
    if pnl < 0:
        return "🔴"
    return "⚪"


def format_duration_short(opened_at: datetime, closed_at: datetime) -> str:
    total_seconds = int((closed_at - opened_at).total_seconds())

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}h{minutes:02d}m{seconds:02d}s"
    if minutes > 0:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def format_sell_telegram(
    pair: str,
    pnl: float,
    pct: float,
    reason: str,
    duration: str,
) -> str:
    emoji = get_pnl_emoji(pnl)
    return (
        f"SELL | {pair}\n"
        f"{emoji} {pnl:+.2f} USDC ({pct:+.2f}%)\n"
        f"{reason} | {duration}"
    )


class PositionStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    STOPPED = "STOPPED"


class CloseReason(Enum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    MOMENTUM_REVERSAL = "MOMENTUM_REVERSAL"
    MANUAL = "MANUAL"

    # NOVOS
    DYNAMIC_PROFIT_PROTECTION = "DYNAMIC_PROFIT_PROTECTION"
    DYNAMIC_WEAKNESS = "DYNAMIC_WEAKNESS"
    DYNAMIC_STAGNATION = "DYNAMIC_STAGNATION"
    DYNAMIC_HARD_EXIT = "DYNAMIC_HARD_EXIT"


@dataclass
class Position:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    pair: str = ""
    symbol: str = ""

    entry_price: float = 0.0
    exit_price: float = 0.0

    stop_loss: float = 0.0
    take_profit: float = 0.0
    peak_price: float = 0.0
    trailing_stop_price: float = 0.0
    trailing_active: bool = False

    capital_invested: float = 0.0
    quantity: float = 0.0

    net_pnl_usdc: float = 0.0
    net_pnl_pct: float = 0.0
    fees_paid: float = 0.0

    status: PositionStatus = PositionStatus.OPEN
    close_reason: Optional[CloseReason] = None

    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None

    # =========================
    # DYNAMIC EXIT CORE
    # =========================
    cycles_in_trade: int = 0
    peak_pnl_pct: float = 0.0

    is_premium_override: bool = False
    entry_source: str = "H&A_SIGNAL"


class PositionManager:

    def __init__(self):
        self._positions: Dict[str, Position] = {}
        self._history: List[Position] = []
        self._snapshot_buffer: List[dict] = []
        self._snapshot_buffer_size = 50

        self.penalty_map: Dict[str, int] = {}
        self.last_traded_symbol: Optional[str] = None
        self.lc1 = LC1Logger()

        print("[DEBUG] Entrou no PositionManager __init__")

        self.notifier = TelegramNotifier(
            token="8696491310:AAFtyPpdmE7qJX2c61rPJeDI7gjAlnonazA",
            chat_id="7975792456",
        )

        print("[DEBUG] Notifier criado")

        try:
            print("[DEBUG] TelegramNotifier inicializado com sucesso")
        except Exception as e:
            logger.warning("[TELEGRAM] Falha ao inicializar notifier: %s", e)
            print(f"[DEBUG] Erro Telegram: {e}")

        logger.info("[PositionManager] Iniciado (SAFE + DYNAMIC EXIT).")

    def _normalize_symbol(self, pair=None, symbol=None):
        return str(symbol or pair or "").upper().strip()

    def _is_valid_price(self, price):
        try:
            return price is not None and float(price) > 0
        except:
            return False

    # ========================================================
    # OPEN POSITION
    # ========================================================

    def open_position(
        self,
        pair=None,
        entry_price=None,
        capital_invested=0.0,
        stop_loss=None,
        take_profit=None,
        quantity=None,
        symbol=None,
        is_premium_override=False,
        entry_source="H&A_SIGNAL",
    ):

        symbol_name = self._normalize_symbol(pair, symbol)

        if not self._is_valid_price(entry_price):
            return None

        entry_price = float(entry_price)
        capital_invested = float(capital_invested or 0)

        fee_entry = capital_invested * (TOTAL_ROUND_TRIP_FEE / 2)

        if quantity is None:
            quantity = (capital_invested - fee_entry) / entry_price

        if stop_loss is None:
            stop_loss = entry_price * (1 - STOP_LOSS_PCT)

        if take_profit is None:
            take_profit = entry_price * (1 + TAKE_PROFIT_PCT)

        pos = Position(
            pair=symbol_name,
            symbol=symbol_name,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            peak_price=entry_price,
            capital_invested=capital_invested,
            quantity=quantity,
            fees_paid=fee_entry,
            is_premium_override=bool(is_premium_override),
            entry_source=str(entry_source or "H&A_SIGNAL"),
        )

        self._positions[symbol_name] = pos
        self.last_traded_symbol = symbol_name
        self.lc1.log_buy(
            {
                "mode": "MOCK",
                "trade_id": symbol_name,
                "symbol": pos.symbol,
                "slot_id": symbol_name,
                "entry_price": pos.entry_price,
                "quantity": pos.quantity,
                "notional_usdc": pos.entry_price * pos.quantity,
                "entry_reason": "H&A_SIGNAL",
                "source": "PositionManager",
            }
        )

        buy_msg = (
            f"BUY | {symbol_name}\n"
            f"ENTRY | {entry_price:.8f}\n"
            f"CAPITAL | {capital_invested:.4f} USDC"
        )

        try:
            self.notifier.send(buy_msg)
            print(f"[TELEGRAM BUY ENVIADO] {symbol_name}")
        except Exception as e:
            logger.warning("[TELEGRAM] Falha ao enviar BUY: %s", e)

        return pos

    # ========================================================
    # CORE DINÂMICO
    # ========================================================

    def _get_dynamic_profit_exit_thresholds(self, pos: Position):
        """
        PositionManager contextual v1:
        Ajusta proteção de lucro e estagnação conforme contexto do trade,
        sem trocar thresholds fixos globais.
        """

        mqii_state = "UNKNOWN"
        liquidity_score = 0.0

        try:
            market_context = getattr(pos, "market_context", None)

            if isinstance(market_context, dict):
                mqii_state = str(
                    market_context.get("mqii_state")
                    or market_context.get("state")
                    or "UNKNOWN"
                ).upper()

                liquidity_score = float(
                    market_context.get("liquidity_score")
                    or market_context.get("market_liquidity_score")
                    or 0.0
                )
        except Exception:
            mqii_state = "UNKNOWN"
            liquidity_score = 0.0

        # defaults atuais
        premium_arm = 0.0035
        normal_arm = 0.0025
        strong_arm = 0.0070
        medium_arm = 0.0030
        weak_arm = 0.0015

        premium_keep_factor = 0.60
        normal_keep_factor = 0.45
        strong_keep_factor = 0.60
        medium_keep_factor = 0.50

        weak_floor = 0.0005
        stagnation_profit_peak = 0.0030
        stagnation_mid_loss = -0.0015

        if mqii_state in ("NO_TRADE", "FRACO", "WEAK"):
            premium_arm = 0.0025
            normal_arm = 0.0015
            strong_arm = 0.0045
            medium_arm = 0.0020
            weak_arm = 0.0010
            weak_floor = 0.0002
            stagnation_profit_peak = 0.0020
            stagnation_mid_loss = -0.0010

        elif mqii_state in ("CAUTIOUS", "MODERADO", "SIDEWAYS"):
            premium_arm = 0.0030
            normal_arm = 0.0020
            strong_arm = 0.0055
            medium_arm = 0.0025
            weak_arm = 0.0012
            weak_floor = 0.0003
            stagnation_profit_peak = 0.0025
            stagnation_mid_loss = -0.0012

        elif mqii_state in ("TRADE_OK", "FORTE"):
            premium_arm = 0.0035
            normal_arm = 0.0025
            strong_arm = 0.0070
            medium_arm = 0.0030
            weak_arm = 0.0015
            weak_floor = 0.0005
            stagnation_profit_peak = 0.0030
            stagnation_mid_loss = -0.0015

        elif mqii_state in ("AGGRESSIVE_OK", "MUITO_FORTE"):
            premium_arm = 0.0045
            normal_arm = 0.0030
            strong_arm = 0.0090
            medium_arm = 0.0040
            weak_arm = 0.0020
            weak_floor = 0.0007
            stagnation_profit_peak = 0.0040
            stagnation_mid_loss = -0.0020

        if liquidity_score and liquidity_score < 0.50:
            premium_arm = min(premium_arm, 0.0025)
            normal_arm = min(normal_arm, 0.0015)
            strong_arm = min(strong_arm, 0.0045)
            medium_arm = min(medium_arm, 0.0020)
            weak_arm = min(weak_arm, 0.0010)
            weak_floor = min(weak_floor, 0.0002)
            stagnation_profit_peak = min(stagnation_profit_peak, 0.0020)
            stagnation_mid_loss = max(stagnation_mid_loss, -0.0010)

        return {
            "mqii_state": mqii_state,
            "liquidity_score": liquidity_score,
            "premium_arm": premium_arm,
            "normal_arm": normal_arm,
            "strong_arm": strong_arm,
            "medium_arm": medium_arm,
            "weak_arm": weak_arm,
            "premium_keep_factor": premium_keep_factor,
            "normal_keep_factor": normal_keep_factor,
            "strong_keep_factor": strong_keep_factor,
            "medium_keep_factor": medium_keep_factor,
            "weak_floor": weak_floor,
            "stagnation_profit_peak": stagnation_profit_peak,
            "stagnation_mid_loss": stagnation_mid_loss,
        }

    def _evaluate_dynamic_exit(self, pos: Position, price: float):

        pnl_pct = (price - pos.entry_price) / pos.entry_price

        if pnl_pct > pos.peak_pnl_pct:
            pos.peak_pnl_pct = pnl_pct

        giveback = pos.peak_pnl_pct - pnl_pct

        dynamic_exit = self._get_dynamic_profit_exit_thresholds(pos)

        # ========================================================
        # 🔥 MPP-P — MICRO PROFIT PROTECTION (PREMIUM ONLY)
        # ========================================================
        try:
            if getattr(pos, "is_premium_override", False):

                # lucro mínimo atingido
                if pos.peak_pnl_pct >= dynamic_exit["premium_arm"]:

                    # perdeu força (começou a devolver)
                    if (
                        pnl_pct
                        <= pos.peak_pnl_pct * dynamic_exit["premium_keep_factor"]
                    ):

                        # evita sair cedo demais
                        if pos.cycles_in_trade >= MIN_HOLD_CYCLES:
                            return CloseReason.DYNAMIC_PROFIT_PROTECTION

        except Exception as e:
            print(f"[MPP-P ERROR] {pos.symbol} | erro={e}")

        # ========================================================
        # 🔥 MPP-N — MICRO PROFIT PROTECTION (NORMAL STRONG SETUPS)
        # ========================================================
        try:
            if not getattr(pos, "is_premium_override", False):

                # Setup normal que já mostrou lucro inicial relevante
                if pos.peak_pnl_pct >= dynamic_exit["normal_arm"]:

                    # Protege antes de virar negativo
                    if (
                        pnl_pct > 0
                        and pnl_pct
                        <= pos.peak_pnl_pct * dynamic_exit["normal_keep_factor"]
                    ):

                        if pos.cycles_in_trade >= MIN_HOLD_CYCLES:
                            return CloseReason.DYNAMIC_PROFIT_PROTECTION

        except Exception as e:
            print(f"[MPP-N ERROR] {pos.symbol} | erro={e}")

        # =========================
        # HARD EXIT (INTELIGENTE)
        # =========================
        if pnl_pct <= HARD_EXIT_MAX_LOSS:

            # 🔻 só sai se já segurou mínimo
            if pos.cycles_in_trade < MIN_HOLD_CYCLES:
                return None

            # 🔻 evita sair em ruído leve
            if pnl_pct > HARD_EXIT_MAX_LOSS * 1.2:
                return None

            return CloseReason.DYNAMIC_HARD_EXIT

        # =========================
        # SEGURAR INÍCIO
        # =========================
        if pos.cycles_in_trade < MIN_HOLD_CYCLES:
            return None

        # ========================================================
        # 🔥 BREAK-EVEN DINÂMICO — H&A (ANTI-RUÍDO + MAX PROFIT)
        # ========================================================
        if pnl_pct > 0:  # 🔥 NOVO: só protege lucro real
            if pos.peak_pnl_pct >= dynamic_exit["strong_arm"]:
                if pnl_pct <= pos.peak_pnl_pct * dynamic_exit["strong_keep_factor"]:
                    return CloseReason.DYNAMIC_PROFIT_PROTECTION

        elif pos.peak_pnl_pct >= dynamic_exit["medium_arm"]:
            if pnl_pct <= 0:
                return CloseReason.DYNAMIC_WEAKNESS

            if pnl_pct <= pos.peak_pnl_pct * dynamic_exit["medium_keep_factor"]:
                return CloseReason.DYNAMIC_PROFIT_PROTECTION

        elif pos.peak_pnl_pct >= dynamic_exit["weak_arm"]:
            if pnl_pct <= dynamic_exit["weak_floor"]:
                return CloseReason.DYNAMIC_PROFIT_PROTECTION

        # =========================
        # PROTEÇÃO DE LUCRO
        # =========================
        if pos.peak_pnl_pct >= PROFIT_ARM_LEVEL_1:

            # Se já devolveu tudo e virou negativo,
            # não é mais proteção de lucro; é fraqueza dinâmica.
            if pnl_pct <= 0:
                return CloseReason.DYNAMIC_WEAKNESS

            if (
                pos.peak_pnl_pct >= PROFIT_ARM_LEVEL_3
                and giveback >= PROFIT_GIVEBACK_LEVEL_3
            ):
                return CloseReason.DYNAMIC_PROFIT_PROTECTION

            if (
                pos.peak_pnl_pct >= PROFIT_ARM_LEVEL_2
                and giveback >= PROFIT_GIVEBACK_LEVEL_2
            ):
                return CloseReason.DYNAMIC_PROFIT_PROTECTION

            if giveback >= PROFIT_GIVEBACK_LEVEL_1 * 1.5:
                return CloseReason.DYNAMIC_PROFIT_PROTECTION

        # =========================
        # STAGNATION
        # =========================
        stagnation_cycles_required = max(STAGNATION_CYCLES, MIN_HOLD_CYCLES + 2)
        stagnation_max_pnl = min(STAGNATION_MAX_PNL, 0.0)

        # ========================================================
        # 🔥 STAGNATION ANTECIPADA (PATCH NOVO)
        # ========================================================
        # ========================================================
        # 🔥 STAGNATION DINÂMICA — H&A PATCH
        # ========================================================
        if pos.peak_pnl_pct >= dynamic_exit["stagnation_profit_peak"]:
            min_cycles_for_stagnation = max(MIN_HOLD_CYCLES + 25, 55)
        elif pnl_pct > dynamic_exit["stagnation_mid_loss"]:
            min_cycles_for_stagnation = max(MIN_HOLD_CYCLES + 20, 45)
        else:
            min_cycles_for_stagnation = max(MIN_HOLD_CYCLES + 10, 30)

        if pos.cycles_in_trade >= min_cycles_for_stagnation:
            is_stagnant_range = STAGNATION_MIN_PNL <= pnl_pct <= stagnation_max_pnl
            never_reached_profit_arm = pos.peak_pnl_pct < PROFIT_ARM_LEVEL_1
            still_negative = pnl_pct < 0

            if is_stagnant_range and never_reached_profit_arm and still_negative:
                return CloseReason.DYNAMIC_STAGNATION

        return None

    # ========================================================
    # UPDATE PRICE
    # ========================================================

    def update_price(self, pair=None, price=None, symbol=None):

        symbol_name = self._normalize_symbol(pair, symbol)

        if symbol_name not in self._positions:
            return None

        if not self._is_valid_price(price):
            return None

        price = float(price)
        pos = self._positions[symbol_name]

        pos.cycles_in_trade += 1

        # =========================
        # TEMPO MÍNIMO DE SUSTENTAÇÃO
        # =========================
        hold_seconds = (datetime.utcnow() - pos.opened_at).total_seconds()
        min_dynamic_hold_seconds = 90

        # =========================
        # CÁLCULO DE PNL
        # =========================
        pnl_pct = (price - pos.entry_price) / pos.entry_price

        # =========================
        # FAST FAILURE CUT
        # =========================
        # Se o trade falha rápido logo após a entrada,
        # corta antes de virar loss grande.

        # =========================
        # FAST FAILURE CUT — DINÂMICO v1
        # =========================
        if pos.peak_pnl_pct <= 0:
            fast_cut_1 = -0.0015
            fast_cut_2 = -0.0024
        elif pos.peak_pnl_pct < 0.0015:
            fast_cut_1 = -0.0018
            fast_cut_2 = -0.0026
        else:
            fast_cut_1 = -0.0020
            fast_cut_2 = -0.0028

        # ========================================================
        # 🔥 FAST FAILURE CUT — AJUSTE H&A (RESPIRAÇÃO INICIAL)
        # ========================================================

        min_hold_before_cut = 10  # 🔥 NOVO: deixa o trade respirar

        if hold_seconds <= 20 and pnl_pct <= fast_cut_1:
            if hold_seconds >= min_hold_before_cut:
                return CloseReason.STOP_LOSS

        if hold_seconds <= 90 and pnl_pct <= fast_cut_2:
            if hold_seconds >= min_hold_before_cut:
                return CloseReason.STOP_LOSS

        # =========================
        # HARD STOP INTELIGENTE — H&A PATCH
        # =========================

        max_loss_absolute = -0.005  # -0.5%

        # ========================================================
        # 🔥 EARLY STOP DINÂMICO — H&A PATCH
        # ========================================================
        # Antes: podia stopar em poucos segundos.
        # Agora: só corta antes de 15s se for perda emergencial.
        # Perdas normais precisam de tempo mínimo de confirmação.
        # ========================================================

        emergency_loss = -0.0045  # -0.45%
        early_confirmed_loss = -0.0028  # -0.28%

        if hold_seconds < 10:
            if pnl_pct <= emergency_loss:
                return CloseReason.STOP_LOSS

        elif hold_seconds < 15:
            if pnl_pct <= early_confirmed_loss:
                return CloseReason.STOP_LOSS

        # 🔥 Se já passou fase inicial → aplica limite completo
        if pnl_pct <= max_loss_absolute:
            return CloseReason.STOP_LOSS

        if price > pos.peak_price:
            pos.peak_price = price

        # =========================
        # STOP FIXO
        # Respeita hold mínimo
        # =========================
        if hold_seconds >= min_dynamic_hold_seconds:
            if price <= pos.stop_loss:
                return CloseReason.STOP_LOSS

        # =========================
        # TAKE PROFIT → ATIVA TRAILING (NÃO SAI IMEDIATO)
        # =========================
        if price >= pos.take_profit:
            pos.trailing_active = True

            if pos.trailing_stop_price == 0:
                pos.trailing_stop_price = price * (1 - TRAILING_STOP_PCT)

        # NÃO fecha posição aqui
        # deixa o trailing decidir saída

        # =========================
        # TRAILING
        # =========================
        profit = (pos.peak_price - pos.entry_price) / pos.entry_price

        if hold_seconds >= min_dynamic_hold_seconds:
            if profit >= TRAILING_ACTIVATION_PCT:
                pos.trailing_active = True
                pos.trailing_stop_price = pos.peak_price * (1 - TRAILING_STOP_PCT)

                if price <= pos.trailing_stop_price:
                    return CloseReason.TRAILING_STOP

        # =========================
        # DYNAMIC EXIT
        # =========================
        if DYNAMIC_EXIT_ENABLED:
            dynamic_reason = self._evaluate_dynamic_exit(pos, price)
            if dynamic_reason:
                return dynamic_reason

        return None

    def monitor_all(self, price_map):
        events = []

        for symbol_name, pos in list(self._positions.items()):
            price = price_map.get(symbol_name)

            if not self._is_valid_price(price):
                continue

            reason = self.update_price(symbol=symbol_name, price=price)

            if reason:
                events.append(
                    {
                        "symbol": symbol_name,
                        "price": price,
                        "reason": reason,
                        "position": pos,
                    }
                )

        return events

    # ========================================================
    # CLOSE POSITION
    # ========================================================

    def close_position(self, pair=None, exit_price=None, reason=None, symbol=None):

        symbol_name = self._normalize_symbol(pair, symbol)

        if symbol_name not in self._positions:
            return None

        exit_price = float(exit_price)
        pos = self._positions.pop(symbol_name)

        reason_value = reason.value if hasattr(reason, "value") else str(reason)

        gross_pct = (exit_price - pos.entry_price) / pos.entry_price
        net_pct = gross_pct - TOTAL_ROUND_TRIP_FEE
        net_usdc = pos.capital_invested * net_pct

        pos.exit_price = exit_price
        pos.net_pnl_pct = net_pct
        pos.net_pnl_usdc = net_usdc
        pos.close_reason = reason
        pos.closed_at = datetime.utcnow()

        duration_seconds = int((pos.closed_at - pos.opened_at).total_seconds())

        pos.status = PositionStatus.CLOSED
        self._history.append(pos)

        # ======================================================
        # 🔥 REGISTRO PARA DECISION ENGINE (ANTI-REENTRADA BURRA)
        # ======================================================
        try:
            if hasattr(self, "decision_engine") and self.decision_engine:
                self.decision_engine.last_trade_was_loss = net_usdc < 0
                self.decision_engine.last_traded_symbol = symbol_name
                self.decision_engine.last_trade_time = datetime.utcnow().timestamp()
                self.decision_engine.last_trade_duration = duration_seconds

                # ======================================================
                # 🔥 CLASSIFICAÇÃO INTELIGENTE DO RESULTADO OPERACIONAL
                # ======================================================

                failure_type = "NONE"

                reason_str = str(
                    reason.value if hasattr(reason, "value") else reason
                ).upper()

                if net_usdc < 0:

                    if "STOP_LOSS" in reason_str:

                        if duration_seconds <= 15:
                            failure_type = "FAST_FAILURE"
                        else:
                            failure_type = "WEAK_CONTINUATION"

                    elif "DYNAMIC_STAGNATION" in reason_str:
                        failure_type = "STAGNATION"

                    elif "DYNAMIC_PROFIT_PROTECTION" in reason_str:
                        failure_type = "WEAK_CONTINUATION"

                    else:
                        failure_type = "GENERIC_LOSS"

                else:

                    if "TAKE_PROFIT" in reason_str:
                        failure_type = "HEALTHY_EXIT"

                    elif "DYNAMIC_PROFIT_PROTECTION" in reason_str:
                        failure_type = "HEALTHY_EXIT"

                self.decision_engine.last_trade_failure_type = failure_type

                logger.info(
                    f"[DRC FAILURE CLASSIFIER] "
                    f"{symbol_name} | "
                    f"type={failure_type} | "
                    f"reason={reason_str} | "
                    f"duration={duration_seconds}s"
                )

        except Exception as e:
            logger.warning(f"[Decision Sync] erro ao registrar último trade: {e}")

        self.lc1.log_sell(
            {
                "mode": "MOCK",
                "trade_id": symbol_name,
                "symbol": pos.symbol,
                "slot_id": symbol_name,
                "exit_price": exit_price,
                "quantity": pos.quantity,
                "gross_pnl": gross_pct,
                "net_pnl": net_usdc,
                "pnl_pct": net_pct,
                "duration_seconds": int(
                    (pos.closed_at - pos.opened_at).total_seconds()
                ),
                "close_reason": reason_value,
                "source": "PositionManager",
            }
        )

        # LEARNING CORE
        if net_usdc > 0:
            self.penalty_map[symbol_name] = max(
                0, self.penalty_map.get(symbol_name, 0) - 1
            )
        else:
            self.penalty_map[symbol_name] = self.penalty_map.get(symbol_name, 0) + 1

        # ======================================================
        # 🔥 DRC MEMORY FEED (NOVO)
        # ======================================================
        if not hasattr(self, "drc_memory"):
            self.drc_memory = {}

        symbol_data = self.drc_memory.get(
            symbol_name,
            {
                "recent_trades": 0,
                "recent_failures": 0,
            },
        )

        # incrementa trades
        symbol_data["recent_trades"] += 1

        # incrementa falhas
        if net_usdc < 0:
            symbol_data["recent_failures"] += 1
        else:
            # reduz falhas em caso de sucesso
            symbol_data["recent_failures"] = max(0, symbol_data["recent_failures"] - 1)

        self.drc_memory[symbol_name] = symbol_data

        logger.info(
            "[CLOSE] %s | pnl=%.4f USDC | reason=%s", symbol_name, net_usdc, reason
        )
        logger.info(self.get_performance_summary_text())

        logger.info(self.get_snapshot_summary_text())

        logger.info(self.get_daily_summary_text())

        duration_str = format_duration_short(pos.opened_at, pos.closed_at)
        sell_msg = format_sell_telegram(
            pair=symbol_name,
            pnl=net_usdc,
            pct=net_pct * 100,
            reason=reason_value,
            duration=duration_str,
        )

        try:

            self.notifier.send(sell_msg)
        except Exception as e:
            logger.warning("[TELEGRAM] Falha ao enviar notificação: %s", e)

        return pos

    # ========================================================
    # GETTERS
    # ========================================================

    def get_all_active(self):
        return list(self._positions.values())

    def get_position(self, pair: Optional[str] = None, symbol: Optional[str] = None):
        symbol_name = self._normalize_symbol(pair, symbol)
        return self._positions.get(symbol_name)

    def has_position(
        self, pair: Optional[str] = None, symbol: Optional[str] = None
    ) -> bool:
        symbol_name = self._normalize_symbol(pair, symbol)
        return symbol_name in self._positions

    def get_active_positions(self):
        return list(self._positions.values())

    def get_history(self):
        return list(self._history)

    def get_performance_metrics(self):
        history = list(self._history)

        total_trades = len(history)
        wins = sum(1 for pos in history if float(pos.net_pnl_usdc) > 0)
        losses = sum(1 for pos in history if float(pos.net_pnl_usdc) < 0)
        breakeven = total_trades - wins - losses

        pnl_total = sum(float(pos.net_pnl_usdc) for pos in history)

        pnl_avg = pnl_total / total_trades if total_trades > 0 else 0.0

        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0.0

        best_trade = max(
            (float(pos.net_pnl_usdc) for pos in history),
            default=0.0,
        )

        worst_trade = min(
            (float(pos.net_pnl_usdc) for pos in history),
            default=0.0,
        )

        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": round(win_rate, 2),
            "pnl_total_usdc": round(pnl_total, 4),
            "pnl_avg_usdc": round(pnl_avg, 4),
            "best_trade_usdc": round(best_trade, 4),
            "worst_trade_usdc": round(worst_trade, 4),
            "open_positions": len(self._positions),
            "penalized_symbols": len([v for v in self.penalty_map.values() if v > 0]),
            "last_traded_symbol": self.last_traded_symbol,
        }

    def get_performance_summary_text(self):
        metrics = self.get_performance_metrics()

        return (
            "[PERFORMANCE] "
            f"trades={metrics['total_trades']} | "
            f"wins={metrics['wins']} | "
            f"losses={metrics['losses']} | "
            f"breakeven={metrics['breakeven']} | "
            f"win_rate={metrics['win_rate']:.2f}% | "
            f"pnl_total={metrics['pnl_total_usdc']:.4f} USDC | "
            f"pnl_avg={metrics['pnl_avg_usdc']:.4f} USDC | "
            f"best={metrics['best_trade_usdc']:.4f} | "
            f"worst={metrics['worst_trade_usdc']:.4f} | "
            f"open_positions={metrics['open_positions']} | "
            f"penalized_symbols={metrics['penalized_symbols']} | "
            f"last_symbol={metrics['last_traded_symbol']}"
        )

    def get_health_check(self) -> dict:
        try:
            metrics = self.get_performance_metrics()
        except Exception as e:
            return {
                "status": "CRITICAL",
                "message": f"Erro ao obter métricas: {e}",
            }

        total_trades = metrics.get("total_trades", 0)
        open_positions = metrics.get("open_positions", 0)

        history = list(self._history)

        last_trade_at = None
        seconds_since_last_trade = None

        if history:
            last_trade = history[-1]
            if last_trade.closed_at:
                last_trade_at = last_trade.closed_at.isoformat()
                seconds_since_last_trade = int(
                    (datetime.utcnow() - last_trade.closed_at).total_seconds()
                )

        # =========================
        # CLASSIFICAÇÃO DE SAÚDE
        # =========================
        status = "HEALTHY"
        message = "Sistema operando normalmente"

        if metrics is None:
            status = "CRITICAL"
            message = "Métricas indisponíveis"

        elif open_positions < 0:
            status = "CRITICAL"
            message = "Estado inválido de posições"

        elif total_trades == 0:
            status = "WARNING"
            message = "Sistema sem trades registrados ainda"

        elif seconds_since_last_trade is not None and seconds_since_last_trade > 1800:
            status = "WARNING"
            message = "Sem trades há muito tempo"

        return {
            "status": status,
            "message": message,
            "total_trades": total_trades,
            "open_positions": open_positions,
            "last_trade_at": last_trade_at,
            "seconds_since_last_trade": seconds_since_last_trade,
        }

    def get_snapshot_passive(self) -> dict:
        metrics = self.get_performance_metrics()

        health = None
        if hasattr(self, "get_health_check"):
            try:
                health = self.get_health_check()
            except Exception as e:
                health = {
                    "status": "CRITICAL",
                    "message": f"Erro ao obter health check: {e}",
                }
        else:
            health = {
                "status": "UNAVAILABLE",
                "message": "Health check ainda não implementado neste arquivo",
            }

        active_positions = self.get_active_positions()

        active_symbols = [pos.symbol for pos in active_positions]
        active_pairs = [pos.pair for pos in active_positions]

        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "performance": metrics,
            "health": health,
            "state": {
                "open_positions": len(active_positions),
                "active_symbols": active_symbols,
                "active_pairs": active_pairs,
                "last_traded_symbol": self.last_traded_symbol,
                "penalty_map_size": len(self.penalty_map),
            },
        }

        return snapshot

    def get_snapshot_summary_text(self) -> str:
        snapshot = self.get_snapshot_passive()

        health = snapshot.get("health", {})
        performance = snapshot.get("performance", {})
        state = snapshot.get("state", {})

        return (
            "[SNAPSHOT] "
            f"health={health.get('status')} | "
            f"health_msg={health.get('message')} | "
            f"trades={performance.get('total_trades')} | "
            f"wins={performance.get('wins')} | "
            f"losses={performance.get('losses')} | "
            f"win_rate={performance.get('win_rate')}% | "
            f"pnl_total={performance.get('pnl_total_usdc'):.4f} USDC | "
            f"open_positions={state.get('open_positions')} | "
            f"last_symbol={state.get('last_traded_symbol')} | "
            f"active_symbols={state.get('active_symbols')}"
        )

    def get_daily_summary_text(self) -> str:
        metrics = self.get_performance_metrics()

        health = None
        if hasattr(self, "get_health_check"):
            try:
                health = self.get_health_check()
            except Exception as e:
                health = {
                    "status": "CRITICAL",
                    "message": f"Erro ao obter health check: {e}",
                }
        else:
            health = {
                "status": "UNAVAILABLE",
                "message": "Health check ainda não implementado",
            }

        snapshot = self.get_snapshot_passive()

        return (
            "[DAILY SUMMARY] "
            f"health={health.get('status')} | "
            f"health_msg={health.get('message')} | "
            f"trades={metrics['total_trades']} | "
            f"wins={metrics['wins']} | "
            f"losses={metrics['losses']} | "
            f"breakeven={metrics['breakeven']} | "
            f"win_rate={metrics['win_rate']:.2f}% | "
            f"pnl_total={metrics['pnl_total_usdc']:.4f} USDC | "
            f"pnl_avg={metrics['pnl_avg_usdc']:.4f} USDC | "
            f"best={metrics['best_trade_usdc']:.4f} | "
            f"worst={metrics['worst_trade_usdc']:.4f} | "
            f"open_positions={snapshot['state']['open_positions']} | "
            f"last_symbol={snapshot['state']['last_traded_symbol']} | "
            f"penalized_symbols={metrics['penalized_symbols']}"
        )

    def register_snapshot(self):
        try:
            snapshot = self.get_snapshot_passive()
            self._snapshot_buffer.append(snapshot)

            if len(self._snapshot_buffer) > self._snapshot_buffer_size:
                self._snapshot_buffer.pop(0)
        except Exception as e:
            logger.warning(f"[SNAPSHOT BUFFER ERROR] {e}")

    def get_snapshot_buffer(self):
        return list(self._snapshot_buffer)

    def get_penalty_map(self):
        return dict(self.penalty_map)

    def get_last_traded_symbol(self):
        return self.last_traded_symbol

    def reset(self):
        self._positions.clear()
        self._history.clear()
        self._snapshot_buffer.clear()
        self.penalty_map.clear()
        self.last_traded_symbol = None
        logger.info("[PositionManager] Reset completo.")
