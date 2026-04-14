# ============================================================
# core/scanner/opportunity_scanner.py
# Radar de oportunidades do H&A
# ============================================================

from concurrent.futures import ThreadPoolExecutor, as_completed

from core.scanner.market_scanner import MarketScanner
from core.scanner.technical_scanner import TechnicalScanner


class OpportunityScanner:

    def __init__(self, client):

        self.client = client

        self.market_scanner = MarketScanner(client)
        self.technical_scanner = TechnicalScanner(client)

    def scan(self, limit=40):

        symbols = self.market_scanner.get_top_liquid_usdc_pairs(
            limit=limit
        )

        print(f"[SCANNER] símbolos brutos recebidos do MarketScanner: {len(symbols)}")

        if symbols:
            preview = symbols[:10]
            print(f"[SCANNER] preview símbolos: {preview}")
        else:
            print("[SCANNER] nenhum símbolo bruto recebido")

        results = []

        # paralelismo
        with ThreadPoolExecutor(max_workers=8) as executor:

            futures = {
                executor.submit(
                    self.technical_scanner.analyze_symbol,
                    symbol
                ): symbol for symbol in symbols
            }

            for future in as_completed(futures):

                symbol = futures[future]

                try:

                    analysis = future.result()

                    if analysis:
                        results.append(analysis)
                    else:
                        print(f"[SCANNER] análise vazia/None para {symbol}")

                except Exception as e:

                    print(f"[SCANNER] erro analisando {symbol}: {e}")

        print(f"[SCANNER] análises válidas finais: {len(results)}")

        if results:
            preview_valid = [item.get("symbol") for item in results[:10]]
            print(f"[SCANNER] preview análises válidas: {preview_valid}")
        else:
            print("[SCANNER] nenhuma análise válida retornada")

        return results
    