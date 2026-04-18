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


class PositionManager:

    def __init__(self):
        self._positions: Dict[str, Position] = {}
        self._history: List[Position] = []

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
            print("[DEBUG] Enviando teste Telegram...")
            self.notifier.send("PositionManager online 🚀")
            print("[DEBUG] Envio Telegram executado")
        except Exception as e:
            logger.warning("[TELEGRAM] Falha no teste inicial: %s", e)
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

        # =========================
        # TELEGRAM BUY
        # =========================
        try:
            self.notifier.send(
                f"BUY {symbol_name} | entrada={pos.entry_price:.8f} | capital={capital_invested:.4f} USDC"
            )
        except Exception as e:
            logger.warning("[TELEGRAM] Falha ao enviar notificação BUY: %s", e)


        return pos

    # ========================================================
    # CORE DINÂMICO
    # ========================================================

    def _evaluate_dynamic_exit(self, pos: Position, price: float):

        pnl_pct = (price - pos.entry_price) / pos.entry_price
        pos.cycles_in_trade += 1

        if pnl_pct > pos.peak_pnl_pct:
            pos.peak_pnl_pct = pnl_pct

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

        # =========================
        # PROTEÇÃO DE LUCRO
        # =========================
        if pos.peak_pnl_pct >= PROFIT_ARM_LEVEL_1:
            giveback = pos.peak_pnl_pct - pnl_pct

            # 🔒 REGRA CRÍTICA — nunca fechar no prejuízo
            if pnl_pct <= 0:
                return None

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

            if giveback >= PROFIT_GIVEBACK_LEVEL_1:
                return CloseReason.DYNAMIC_PROFIT_PROTECTION

        # =========================
        # STAGNATION
        # =========================
        stagnation_cycles_required = max(STAGNATION_CYCLES, MIN_HOLD_CYCLES + 2)
        stagnation_max_pnl = min(STAGNATION_MAX_PNL, 0.0)

        min_cycles_for_stagnation = max(stagnation_cycles_required, 90)

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

        # =========================
        # 🔒 HARD STOP ABSOLUTO (NOVO)
        # =========================
        pnl_pct = (price - pos.entry_price) / pos.entry_price

        if pnl_pct <= -0.005:  # -0.5% máximo absoluto
            return CloseReason.STOP_LOSS

        # =========================
        # TEMPO MÍNIMO DE SUSTENTAÇÃO
        # =========================
        hold_seconds = (datetime.utcnow() - pos.opened_at).total_seconds()
        min_dynamic_hold_seconds = 90

        if price > pos.peak_price:
            pos.peak_price = price

        
        # =========================
        # STOP FIXO
        # =========================
        if price <= pos.stop_loss:
            return CloseReason.STOP_LOSS

        # =========================
        # TAKE PROFIT → ATIVA TRAILING (NÃO SAI IMEDIATO)
        # =========================
        if price >= pos.take_profit:
            pos.trailing_active = True

        # só ativa se ainda não estava ativo
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
        if DYNAMIC_EXIT_ENABLED and hold_seconds >= min_dynamic_hold_seconds:
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

        pos.status = PositionStatus.CLOSED
        self._history.append(pos)

        # ======================================================
        # 🔥 REGISTRO PARA DECISION ENGINE (ANTI-REENTRADA BURRA)
        # ======================================================
        try:
            if hasattr(self, "decision_engine") and self.decision_engine:
                self.decision_engine.last_trade_was_loss = net_usdc < 0
                self.decision_engine.last_traded_symbol = symbol_name
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

        logger.info(
            "[CLOSE] %s | pnl=%.4f USDC | reason=%s", symbol_name, net_usdc, reason
        )

        try:
            self.notifier.send(
                f"SELL {symbol_name} | pnl={net_usdc:.4f} USDC | motivo={reason_value}"
            )
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

    def get_penalty_map(self):
        return dict(self.penalty_map)

    def get_last_traded_symbol(self):
        return self.last_traded_symbol

    def reset(self):
        self._positions.clear()
        self._history.clear()
        self.penalty_map.clear()
        self.last_traded_symbol = None
        logger.info("[PositionManager] Reset completo.")
