# ============================================================
# core/orchestrator/trading_orchestrator.py
# Orquestrador principal do H&A
# ============================================================

from core.scanner.opportunity_scanner import OpportunityScanner
from core.scanner.opportunity_gate import OpportunityGate


class TradingOrchestrator:

    def __init__(self, client, slot_controller):

        self.client = client
        self.slot_controller = slot_controller

        self.scanner = OpportunityScanner(client)


    def scan_market(self):

        ranked = self.scanner.scan()

        opportunities = OpportunityGate.filter(ranked)

        return opportunities


    def allocate_slots(self):

        opportunities = self.scan_market()

        if not opportunities:
            print("Nenhuma oportunidade encontrada")
            return

        for op in opportunities:

            symbol = op["symbol"]

            if self.slot_controller.has_free_slot():

                slot = self.slot_controller.allocate(symbol)

                print(f"Slot {slot} reservado para {symbol}")

            else:

                print("Sem slots livres")
                break