# ============================================================
# main.py
# Entry point do sistema H&A
# SAFE BOOT VERSION — DYNAMIC POLICY + LC1 + RADAR ÚNICO
# ============================================================

import threading

from binance.client import Client

from core.executor.binance_executor import BinanceExecutor
from core.executor.mock_executor import MockExecutor
from core.risk.risk_manager import RiskManager
from core.radar.market_radar_engine import MarketRadarEngine
from core.slot_controller import SlotController
from core.loop.auto_loop import AutoLoop
from core.position.position_manager import PositionManager
from core.position.position_tracker import PositionTracker
from core.capital_engine.capital_allocator import CapitalAllocator
from core.decision.decision_engine import DecisionEngine
from core.dynamic_policy.lc1_feedback_adapter import LC1FeedbackAdapter

from interface.desktop.app_layout import HAControlPanel
from interface.desktop.ha_controller import HAController
from core.notifications.telegram_notifier import TelegramNotifier

from core.credentials.api_keys import (
    get_binance_api_key,
    get_binance_api_secret,
)

from core.execution_mode import set_execution_mode, get_execution_mode, ExecutionMode


# ============================================================
# POSITION SYNC
# Reconstrói posições abertas consultando a Binance
# ============================================================


def sync_positions_with_binance(client, slot_controller, position_manager):
    print("\n===================================")
    print("   POSITION SYNC - BINANCE WALLET")
    print("===================================\n")

    try:
        account = client.get_account()
        balances = account.get("balances", [])
        slots = list(slot_controller.get_slots().values())
        slot_index = 0

        for balance in balances:
            asset = balance.get("asset")
            free_amount = float(balance.get("free", 0.0))

            if asset in ("USDC", "USDT", "BNB"):
                continue

            if free_amount <= 0:
                continue

            symbol = f"{asset}USDC"

            try:
                ticker = client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker["price"])
            except Exception:
                continue

            if slot_index >= len(slots):
                break

            slot = slots[slot_index]
            slot_index += 1

            try:
                position_manager.open_position(
                    symbol=symbol,
                    entry_price=current_price,
                    quantity=free_amount,
                )

                slot.pair = symbol
                slot.entry_price = current_price
                slot.quantity = free_amount
                slot._state = "RUNNING"

                print(
                    f"[SYNC] slot={slot.slot_id} | "
                    f"pair={symbol} | qty={free_amount:.8f} | "
                    f"entry~={current_price:.8f}"
                )

            except Exception as e:
                print(f"[SYNC] erro ao registrar posição {symbol}: {e}")

        print("\n[SYNC] concluído.\n")

    except Exception as e:
        print(f"[SYNC] erro geral: {e}")


# ============================================================
# CLIENTE BINANCE
# ============================================================


def build_client(current_mode: ExecutionMode) -> Client:
    api_key = get_binance_api_key()
    api_secret = get_binance_api_secret()

    if current_mode == ExecutionMode.LIVE:
        client = Client(api_key, api_secret)
        print("[BOOT] Binance client LIVE iniciado")
        return client

    client = Client("", "")
    print("[BOOT] Binance client público iniciado (MOCK seguro)")
    return client


# ============================================================
# EXECUTOR
# ============================================================


def build_executor(
    current_mode: ExecutionMode,
    client: Client,
    position_manager: PositionManager,
    tracker: PositionTracker,
    notifier=None,
):

    if current_mode == ExecutionMode.LIVE:
        executor = BinanceExecutor(
            client=client,
            position_manager=position_manager,
            tracker=tracker,
            notifier=notifier,
        )
        print("[BOOT] BinanceExecutor iniciado (LIVE)")
        return executor

    executor = MockExecutor(
        client=client,
        position_manager=position_manager,
        tracker=tracker,
        initial_balance=1000.0,
        notifier=notifier,
    )
    print("[BOOT] MockExecutor iniciado (assinatura completa)")
    return executor


# ============================================================
# MAIN
# ============================================================


def main():
    print("\n===================================")
    print("   H&A System Boot")
    print("===================================\n")

    # --------------------------------------------------------
    # EXECUTION MODE
    # --------------------------------------------------------
    set_execution_mode(ExecutionMode.MOCK)
    current_mode = get_execution_mode()
    print(f"[BOOT] Modo selecionado: {current_mode}")

    # --------------------------------------------------------
    # CLIENT
    # --------------------------------------------------------
    client = build_client(current_mode)

    telegram_notifier = TelegramNotifier(
        token="8696491310:AAFtyPpdmE7qJX2c61rPJeDI7gjAlnonazA",
        chat_id="7975792456",
    )

    # --------------------------------------------------------
    # POSITION CORE
    # --------------------------------------------------------
    position_manager = PositionManager()
    print("PositionManager iniciado")

    tracker = PositionTracker()
    print("PositionTracker iniciado")

    # --------------------------------------------------------
    # EXECUTOR
    # --------------------------------------------------------
    executor = build_executor(
        current_mode=current_mode,
        client=client,
        position_manager=position_manager,
        tracker=tracker,
        notifier=telegram_notifier,
    )

    # --------------------------------------------------------
    # BALANCE
    # --------------------------------------------------------
    try:
        balance = float(executor.get_balance("USDC"))
    except Exception:
        balance = 0.0

    print(f"Saldo USDC detectado: {balance}")

    # --------------------------------------------------------
    # RISK MANAGER
    # --------------------------------------------------------
    risk_manager = RiskManager(executor)
    print("RiskManager iniciado")

    # --------------------------------------------------------
    # CAPITAL ALLOCATOR
    # --------------------------------------------------------
    capital_allocator = CapitalAllocator(executor)
    print("CapitalAllocator iniciado")

    # --------------------------------------------------------
    # LC1 FEEDBACK
    # --------------------------------------------------------
    lc1_adapter = LC1FeedbackAdapter()
    print("LC1FeedbackAdapter iniciado")

    # --------------------------------------------------------
    # DECISION ENGINE
    # --------------------------------------------------------
    decision_engine = DecisionEngine(
        risk_manager=risk_manager,
        capital_allocator=capital_allocator,
        lc1_adapter=lc1_adapter,
    )
    print("DecisionEngine iniciado")

    
    # --------------------------------------------------------
    # RADAR
    # --------------------------------------------------------
    radar = MarketRadarEngine(client)
    radar.start()

    # --------------------------------------------------------
    # SLOT CONTROLLER
    # --------------------------------------------------------
    slot_controller = SlotController(
    slot_ids=[1, 2, 3, 4],
    decision_engine=decision_engine,
    client=client,
    executor=executor,
    risk_manager=risk_manager,
)

    slot_controller.market_radar = radar
    slot_controller.balance = balance
    slot_controller.position_manager = position_manager
    slot_controller.lc1_adapter = lc1_adapter

    decision_engine.set_system_context_provider(slot_controller)
    decision_engine.set_position_manager(position_manager)
    position_manager.decision_engine = decision_engine

    print("SlotController iniciado")

    # --------------------------------------------------------
    # POSITION SYNC
    # --------------------------------------------------------
    if current_mode == ExecutionMode.LIVE:
        sync_positions_with_binance(
            client=client,
            slot_controller=slot_controller,
            position_manager=position_manager,
        )
    else:
        print("[BOOT] POSITION SYNC ignorado em MOCK")

    # --------------------------------------------------------
    # AUTO LOOP
    # --------------------------------------------------------
    auto_loop = AutoLoop(
        slot_controller=slot_controller,
        interval_seconds=2,
    )

    print("\n===================================")
    print("AutoLoop pronto (aguardando START da UI)")
    print("===================================\n")

    
        
    ha_controller = HAController(
        auto_loop=auto_loop,
        slot_controller=slot_controller,
        executor=executor,
        position_manager=position_manager,
        telegram_notifier=telegram_notifier,
    )

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------
    # 🔥 CONEXÃO DO RADAR (AQUI)
    auto_loop.market_radar = radar
    auto_loop.radar = radar

    ha_controller.market_radar = radar
    ha_controller.radar = radar

    # UI
    app = HAControlPanel(
        controller=ha_controller,
        auto_loop=auto_loop,
    )

    app.mainloop()


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()
