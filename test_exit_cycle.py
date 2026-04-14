# ============================================================
# TESTE DO CICLO DE SAÍDA DO H&A
# ============================================================

from binance.client import Client

from core.executor.binance_executor import BinanceExecutor
from core.slot_engine.slot_controller import SlotController
from core.slot_engine.slot_state_machine import SlotState
from core.slot.slot_trading_loop import SlotTradingLoop

# ------------------------------------------------
# SUAS CHAVES BINANCE
# ------------------------------------------------

API_KEY = "XhLJ00oyaxMtssBcCBqvcokzTQy5hFY3N67CSHRUfuuL3LTXpYnsNWsGNIKYFvvO"
SECRET_KEY = "FOKEHS57A5fKWBhY30My6dEWzz7POQrhuGyX1Uw1l2JiMrCP7AXK4839SjiKMpiR"

# ------------------------------------------------
# CLIENT BINANCE
# ------------------------------------------------

print("Criando client...")

client = Client(API_KEY, SECRET_KEY)

print("Criando executor...")

executor = BinanceExecutor(client)

# ------------------------------------------------
# SLOT
# ------------------------------------------------

print("Criando slot...")

slot = SlotController(slot_id=1)

slot.assign_asset("BTCUSDC")

# ------------------------------------------------
# LOOP
# ------------------------------------------------

print("Criando loop de trading...")

slot_loop = SlotTradingLoop(
    slot_controller=slot,
    decision_engine=None,
    executor=executor
)

# ------------------------------------------------
# SIMULAR POSIÇÃO ABERTA
# ------------------------------------------------

print("Simulando posição aberta...")

slot_loop.position_tracker.open_position(
    symbol="BTCUSDC",
    entry_price=70000,
    quantity=0.0002
)

# ------------------------------------------------
# FORÇAR SLOT EM TRADING
# ------------------------------------------------

slot.state = SlotState.TRADING

# ------------------------------------------------
# EXECUTAR CICLO
# ------------------------------------------------

print("Executando ciclo do slot...")

result = slot_loop.run_cycle(active_positions=1)

print("RESULTADO:")
print(result)