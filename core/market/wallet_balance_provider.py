from binance.client import Client


class WalletBalanceException(Exception):
    pass


class WalletBalanceProvider:
    """
    Responsável por buscar saldo real USDC da Binance Spot.
    """

    def __init__(self, client: Client):
        if client is None:
            raise ValueError("Client da Binance não pode ser None.")
        self._client = client

    # --------------------------------------------------------
    # MÉTODO PRINCIPAL
    # --------------------------------------------------------

    def get_usdc_balance(self) -> dict:
        try:
            balance = self._client.get_asset_balance(asset="USDC")

            if not balance:
                raise WalletBalanceException(
                    "Não foi possível obter saldo USDC."
                )

            free = float(balance["free"])
            locked = float(balance["locked"])
            total = free + locked

            return {
                "asset": "USDC",
                "free": free,
                "locked": locked,
                "total": total
            }

        except Exception as e:
            raise WalletBalanceException(
                f"Erro ao buscar saldo USDC: {str(e)}"
            )