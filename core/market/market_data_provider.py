# ============================================================
# MarketDataProvider
# Fonte oficial de dados Spot USDC - Binance
# H&A - MarketSnapshotContract v1.0
# ============================================================

from binance.client import Client
from binance.exceptions import BinanceAPIException
import time


class MarketDataException(Exception):
    """Exceção controlada para falhas no MarketDataProvider."""
    pass


class MarketDataProvider:

    def __init__(self, client: Client):
        if client is None:
            raise ValueError("Client da Binance não pode ser None.")
        self.client = client

    # ============================================================
    # Validação de símbolo
    # ============================================================
    def _validate_symbol(self, symbol: str):
        if not symbol.endswith("USDC"):
            raise MarketDataException(
                f"Símbolo inválido para o H&A: {symbol}. Apenas pares USDC são permitidos."
            )

    # ============================================================
    # Preço atual (mantido por compatibilidade)
    # ============================================================
    def get_price(self, symbol: str) -> dict:

        self._validate_symbol(symbol)

        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)

            if "price" not in ticker:
                raise MarketDataException(
                    f"Resposta inesperada da Binance para {symbol}: {ticker}"
                )

            price = float(ticker["price"])

            return {
                "symbol": symbol,
                "price": price,
                "timestamp": int(time.time())
            }

        except BinanceAPIException as e:
            raise MarketDataException(
                f"Erro da API Binance ao buscar preço de {symbol}: {str(e)}"
            )

        except Exception as e:
            raise MarketDataException(
                f"Erro inesperado ao buscar preço de {symbol}: {str(e)}"
            )

    # ============================================================
    # Candles (NOVO - Base do Snapshot)
    # ============================================================
    def get_candles(
        self,
        symbol: str,
        interval: str = Client.KLINE_INTERVAL_1MINUTE,
        limit: int = 100
    ) -> list:

        self._validate_symbol(symbol)

        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )

            if not klines or len(klines) < 50:
                raise MarketDataException(
                    f"Quantidade insuficiente de candles para {symbol}"
                )

            candles = []

            for k in klines:
                candles.append({
                    "timestamp": int(k[0] / 1000),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5])
                })

            return candles

        except BinanceAPIException as e:
            raise MarketDataException(
                f"Erro da API Binance ao buscar candles de {symbol}: {str(e)}"
            )

        except Exception as e:
            raise MarketDataException(
                f"Erro inesperado ao buscar candles de {symbol}: {str(e)}"
            )