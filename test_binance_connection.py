# ============================================================
# test_binance_connection.py
# Teste simples de conexão com Binance
# NÃO executa trades
# ============================================================

from binance.client import Client
from core.execution_mode import set_execution_mode, ExecutionMode
from core.credentials.api_keys import get_binance_api_key, get_binance_api_secret

set_execution_mode(ExecutionMode.LIVE)


def main():

    print("\n===============================")
    print("H&A Binance Connection Test")
    print("===============================\n")

    try:

        client = Client(
    get_binance_api_key(),
    get_binance_api_secret()
)

        print("Client criado com sucesso")

        # testar comunicação com Binance
        server_time = client.get_server_time()

        print("Conexão com Binance OK")
        print("Server time:", server_time)

        # testar leitura de saldo
        balance = client.get_asset_balance(asset="USDC")

        if balance:
            print("Saldo USDC:", balance["free"])
        else:
            print("Saldo USDC não encontrado")

    except Exception as e:

        print("ERRO NA CONEXÃO:")
        print(e)


if __name__ == "__main__":
    main()