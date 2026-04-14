from binance.client import Client


class SymbolMetadataException(Exception):
    pass


class SymbolMetadataProvider:
    """
    Responsável por buscar e cachear metadados do símbolo na Binance.

    Retorna:
    - step_size
    - min_notional
    """

    def __init__(self, client: Client):
        if client is None:
            raise ValueError("Client da Binance não pode ser None.")
        self._client = client
        self._cache = {}

    def get_metadata(self, symbol: str) -> dict:

        if symbol in self._cache:
            return self._cache[symbol]

        try:
            info = self._client.get_symbol_info(symbol)

            if not info:
                raise SymbolMetadataException(
                    f"Não foi possível obter informações do símbolo {symbol}"
                )

            filters = {f["filterType"]: f for f in info["filters"]}

            # LOT SIZE
            lot_size = filters.get("LOT_SIZE")
            if not lot_size:
                raise SymbolMetadataException(
                    f"Filtro LOT_SIZE não encontrado para {symbol}"
                )

            step_size = float(lot_size["stepSize"])

            # MIN NOTIONAL (novo ou antigo)
            min_notional_filter = (
                filters.get("MIN_NOTIONAL")
                or filters.get("NOTIONAL")
            )

            if not min_notional_filter:
                raise SymbolMetadataException(
                    f"Filtro NOTIONAL/MIN_NOTIONAL não encontrado para {symbol}"
                )

            min_notional_value = float(
                min_notional_filter.get("minNotional")
                or min_notional_filter.get("notional")
            )

            metadata = {
                "symbol": symbol,
                "step_size": step_size,
                "min_notional": min_notional_value
            }

            self._cache[symbol] = metadata

            return metadata

        except Exception as e:
            raise SymbolMetadataException(
                f"Erro ao obter metadata de {symbol}: {str(e)}"
            )