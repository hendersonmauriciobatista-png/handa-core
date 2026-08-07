# ============================================================
# core/scanner/opportunity_gate.py
# Filtro de oportunidades do H&A
# ============================================================

MIN_MARKET_SCORE = 3


class OpportunityGate:

    @staticmethod
    def filter(ranked_results):

        opportunities = []

        for r in ranked_results:

            score = r.get("score", 0)

            if score < MIN_MARKET_SCORE:
                continue

            opportunities.append(r)

        return opportunities