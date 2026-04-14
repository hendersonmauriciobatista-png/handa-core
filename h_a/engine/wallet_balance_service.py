from binance.client import Client
from binance.exceptions import BinanceAPIException


class WalletBalanceService:

    def __init__(self, api_key: str, api_secret: str):
        self.client = Client(api_key, api_secret)

    def get_usdc_balance(self) -> float:
        try:
            account = self.client.get_account()
            balances = account.get("balances", [])

            for asset in balances:
                if asset.get("asset") == "USDC":
                    return float(asset.get("free", 0.0))

            return 0.0

        except BinanceAPIException as e:
            print("[WalletBalanceService] Binance API error:", e)
            return 0.0

        except Exception as e:
            print("[WalletBalanceService] General error:", e)
            return 0.0
