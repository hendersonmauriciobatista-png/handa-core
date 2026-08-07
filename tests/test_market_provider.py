from binance.client import Client
import os

from core.market.market_data_provider import MarketDataProvider, MarketDataException


def main():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        raise ValueError("API keys não encontradas nas variáveis de ambiente.")

    client = Client(api_key, api_secret)

    provider = MarketDataProvider(client)

    try:
        result = provider.get_price("BTCUSDC")
        print("SUCESSO:")
        print(result)

    except MarketDataException as e:
        print("ERRO CONTROLADO:")
        print(str(e))


if __name__ == "__main__":
    main()