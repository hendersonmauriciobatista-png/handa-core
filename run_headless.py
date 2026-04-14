# ============================================================
# run_headless.py
# H&A — HEADLESS FULL ENGINE (SEM UI)
# ============================================================

import os
import sys

from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

sys.path.append(base_path)


from binance.client import Client

from core.execution_mode import set_execution_mode, ExecutionMode
from executor.mock_executor import MockExecutor
from core.risk.risk_manager import RiskManager
from core.radar.market_radar_engine import MarketRadarEngine
from core.slot_controller import SlotController
from core.loop.auto_loop import AutoLoop
from core.position.position_manager import PositionManager
from core.position.position_tracker import PositionTracker
from core.capital_engine.capital_allocator import CapitalAllocator
from core.decision.decision_engine import DecisionEngine
from core.dynamic_policy.lc1_feedback_adapter import LC1FeedbackAdapter
from core.learning.adaptive_learning_observer import AdaptiveLearningObserver
from core.notifications.telegram_notifier import TelegramNotifier


def run():
    load_dotenv()

    print("\n===================================")
    print("   H&A HEADLESS FULL ENGINE")
    print("===================================\n")

    # ========================================================
    # MODE
    # ========================================================
    set_execution_mode(ExecutionMode.MOCK)
    current_mode = ExecutionMode.MOCK

    telegram_token = os.getenv("TELEGRAM_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # ========================================================
    # CLIENT
    # ========================================================
    client = Client("", "")
    print("[HEADLESS] Client iniciado")

    # ========================================================
    # POSITION CORE
    # ========================================================
    position_manager = PositionManager()
    tracker = PositionTracker()

    # ========================================================
    # EXECUTOR
    # ========================================================
    executor = MockExecutor(
        client=client,
        position_manager=position_manager,
        tracker=tracker,
        initial_balance=1000.0,
    )

    print("[HEADLESS] Executor iniciado")

    # ========================================================
    # RISK + CAPITAL
    # ========================================================
    risk_manager = RiskManager(executor)
    capital_allocator = CapitalAllocator(executor)

    # ========================================================
    # LC1 + ALO
    # ========================================================
    lc1_adapter = LC1FeedbackAdapter()
    alo = AdaptiveLearningObserver()

    notifier = TelegramNotifier(
        token=telegram_token,
        chat_id=telegram_chat_id,
    )

    # ========================================================
    # DECISION ENGINE
    # ========================================================
    decision_engine = DecisionEngine(
        risk_manager=risk_manager,
        capital_allocator=capital_allocator,
        lc1_adapter=lc1_adapter,
    )

    decision_engine.set_alo(alo)

    # ========================================================
    # RADAR
    # ========================================================
    radar = MarketRadarEngine(client)
    radar.start()

    print("[HEADLESS] Radar iniciado")

    # ========================================================
    # SLOT CONTROLLER
    # ========================================================
    slot_controller = SlotController(
        slot_ids=[1, 2, 3, 4],
        decision_engine=decision_engine,
        client=client,
        executor=executor,
        risk_manager=risk_manager,
    )

    slot_controller.market_radar = radar
    slot_controller.position_manager = position_manager
    slot_controller.lc1_adapter = lc1_adapter

    decision_engine.set_system_context_provider(slot_controller)
    decision_engine.set_position_manager(position_manager)

    print("[HEADLESS] SlotController conectado")

    # ========================================================
    # AUTO LOOP
    # ========================================================
    auto_loop = AutoLoop(
        slot_controller=slot_controller,
        interval_seconds=2,
    )

    auto_loop.market_radar = radar
    auto_loop.radar = radar

    print("\n===================================")
    print("   AUTOLOOP HEADLESS INICIADO")
    print("===================================\n")

    notifier.send("🚀 H&A HEADLESS iniciado com sucesso")

    auto_loop.start()


if __name__ == "__main__":
    run()