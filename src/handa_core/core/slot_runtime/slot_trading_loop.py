# ============================================================
# core/slot/slot_trading_loop.py
# Loop de execução de trading por slot
# Com cálculo de Market Strength
# ============================================================

from core.execution.execution_plan import ExecutionPlan
from core.slot_engine.slot_state_machine import SlotState
from core.position.position_tracker import PositionTracker
from core.exit.exit_manager import ExitManager
from core.indicators.indicator_snapshot import IndicatorSnapshot

class SlotTradingLoop:

    def __init__(self, slot_controller, decision_engine, executor):

        self.slot = slot_controller
        self.decision_engine = decision_engine
        self.executor = executor

        self.position_tracker = PositionTracker()
        self.exit_manager = ExitManager()

        # ------------------------------------------------
        # Buffer de snapshots para Market Strength
        # ------------------------------------------------

        self.market_snapshots = []

    # =================================================
    # CICLO PRINCIPAL DO SLOT
    # =================================================

    def run_cycle(self, active_positions: int):

        state = self.slot.get_state()

        # ------------------------------------------------
        # ANALYZING
        # ------------------------------------------------

        if state == SlotState.ANALYZING:

            decision = self.decision_engine.run(
                slot_id=self.slot.slot_id,
                active_positions=active_positions
            )

            if decision.executed:

                symbol = self.slot.get_current_asset()

                plan = ExecutionPlan(
                    symbol=symbol,
                    side="BUY",
                    quantity=decision.quantity,
                    price=decision.price,
                    reason=decision.reason
                )

                result = self.executor.execute_plan(plan)

                fills = result["fills"][0]
                entry_price = float(fills["price"])

                self.position_tracker.open_position(
                    symbol=symbol,
                    entry_price=entry_price,
                    quantity=decision.quantity
                )

                self.slot.execute_trade()

                return result

        # ------------------------------------------------
        # ARMED
        # ------------------------------------------------

        elif state == SlotState.ARMED:

            self.slot.register_armed_cycle()

        # ------------------------------------------------
        # TRADING
        # ------------------------------------------------

        elif state == SlotState.TRADING:

            symbol = self.position_tracker.symbol

            snapshot = self.decision_engine._snapshot_service.get_market_snapshot(symbol)
            
            indicator_snapshot = IndicatorSnapshot(
                ema_10=snapshot["ema_10"],
                ema_20=snapshot["ema_20"],
                ema_50=snapshot["ema_50"],
                rsi_14=snapshot["rsi_14"],
                volume_ratio=snapshot["volume_ratio"]
            )
            # ------------------------------------------------
            # BUFFER DE SNAPSHOTS (3 velas)
            # ------------------------------------------------

            self.market_snapshots.append(indicator_snapshot)

            if len(self.market_snapshots) > 3:
                self.market_snapshots.pop(0)

            # ------------------------------------------------
            # MARKET STRENGTH
            # ------------------------------------------------

            if len(self.market_snapshots) == 3:

                try:

                    strength = self.decision_engine.market_strength_calculator.calculate(
                        self.market_snapshots
                    )

                    print(
                        f"[Slot {self.slot.slot_id}] Market Strength: {strength}%"
                    )

                except Exception as e:

                    print(
                        f"[Slot {self.slot.slot_id}] Erro Market Strength:", e
                    )

            # ------------------------------------------------
            # PNL
            # ------------------------------------------------

            current_price = snapshot["price"]

            pnl_percent = self.position_tracker.calculate_pnl_percent(current_price)

            should_exit, reason = self.exit_manager.should_exit(pnl_percent)

            if should_exit:

                plan = ExecutionPlan(
                    symbol=symbol,
                    side="SELL",
                    quantity=self.position_tracker.quantity,
                    price=current_price,
                    reason=reason
                )

                result = self.executor.execute_plan(plan)

                self.position_tracker.close_position()

                self.slot.exit_trade()

                return result

        return None