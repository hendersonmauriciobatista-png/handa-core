"""
RiskView
Exibe o estado global de risco do sistema H&A.

Regras:
- Linguagem neutra
- Estados explícitos
- Boot ≠ erro
- UI nunca decide
"""

class RiskView:
    def __init__(self):
        pass

    def render(self, state: dict):
        system = state.get("system", {})
        risk = system.get("risk")

        print("\n" + "-" * 60)
        print(" ESTADO GLOBAL DE RISCO ")
        print("-" * 60)

        if risk == "RISK_NORMAL":
            message = "Risco dentro do esperado"
        elif risk == "RISK_ELEVATED":
            message = "Risco elevado — sistema atento"
        elif risk == "RISK_BLOCKED":
            message = "Risco bloqueado — novas operações suspensas"
        elif risk in (None, "UNKNOWN"):
            message = "Risco ainda não avaliado"
        else:
            message = f"Risco inválido ({risk})"

        print(f" {message}")
        print("-" * 60)
