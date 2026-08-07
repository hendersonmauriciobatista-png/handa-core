from binance.client import Client
from core.executor.binance_executor import BinanceExecutor
from core.execution.execution_plan import ExecutionPlan

print("SCRIPT INICIADO")

# ============================================================
# COLOQUE SUAS CHAVES AQUI
# ============================================================

API_KEY = "XhLJ00oyaxMtssBcCBqvcokzTQy5hFY3N67CSHRUfuuL3LTXpYnsNWsGNIKYFvvO"
SECRET_KEY = "FOKEHS57A5fKWBhY30My6dEWzz7POQrhuGyX1Uw1l2JiMrCP7AXK4839SjiKMpiR"

# ============================================================
# CLIENT BINANCE
# ============================================================

print("Criando client...")

client = Client(API_KEY, SECRET_KEY)

# ============================================================
# EXECUTOR
# ============================================================

print("Criando executor...")

executor = BinanceExecutor(client)

# ============================================================
# EXECUTION PLAN
# ============================================================

print("Criando plano...")

plan = ExecutionPlan(
    symbol="BTCUSDC",
    side="BUY",
    quantity=0.0002,
    reason="TEST_EXECUTION"
)

# ============================================================
# EXECUTAR
# ============================================================

print("Executando ordem...")

result = executor.execute_plan(plan)

print("RESULTADO DA ORDEM:")
print(result)