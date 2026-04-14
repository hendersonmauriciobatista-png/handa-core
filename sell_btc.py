from binance.client import Client
from decimal import Decimal, ROUND_DOWN

api_key = "XhLJ00oyaxMtssBcCBqvcokzTQy5hFY3N67CSHRUfuuL3LTXpYnsNWsGNIKYFvvO"
api_secret = "FOKEHS57A5fKWBhY30My6dEWzz7POQrhuGyX1Uw1l2JiMrCP7AXK4839SjiKMpiR"

client = Client(api_key, api_secret)

# 1. Saldo disponível
btc_free = Decimal(client.get_asset_balance(asset="BTC")["free"])

# 2. Buscar regras do par
info = client.get_symbol_info("BTCUSDC")

lot_size_filter = next(
    f for f in info["filters"] if f["filterType"] == "LOT_SIZE"
)

step_size = Decimal(lot_size_filter["stepSize"])

# 3. Ajustar quantidade ao step size
btc_qty = (btc_free // step_size) * step_size
btc_qty = btc_qty.quantize(step_size, rounding=ROUND_DOWN)

print(f"BTC disponível: {btc_free}")
print(f"STEP SIZE: {step_size}")
print(f"BTC para venda (ajustado): {btc_qty}")

# 4. Enviar ordem SELL
order = client.create_order(
    symbol="BTCUSDC",
    side=Client.SIDE_SELL,
    type=Client.ORDER_TYPE_MARKET,
    quantity=str(btc_qty)
)

print(order)
