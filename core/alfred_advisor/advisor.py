from datetime import datetime
import json
from pathlib import Path


HISTORY_FILE = Path("storage/history/integracao_alfred_ha.jsonl")


class AlfredAdvisor:
    """
    ALFRED IA — Advisor Cognitivo
    --------------------------------
    • NÃO executa ações
    • NÃO altera estados
    • NÃO chama executor
    • APENAS registra análises e recomendações
    """

    def __init__(self):
        self.source = "ALFRED_IA"

    def advise(self, contexto: str, descricao: str, recomendacao: str) -> str:
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "origem": self.source,
            "tipo": "decisao_assistida",
            "contexto": contexto,
            "descricao": descricao,
            "resultado": recomendacao
        }
        self._log(event)
        return recomendacao

    def _log(self, event: dict):
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def validate_before_live(self, descricao: str, recomendacao: str) -> bool:
        """
        Validação cognitiva antes de qualquer execução LIVE.
        Retorna True (liberado) ou False (bloqueado).
        """
        decision = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "origem": self.source,
            "tipo": "validacao_pre_live",
            "contexto": "live",
            "descricao": descricao,
            "resultado": recomendacao
        }
        self._log(decision)
        return recomendacao.lower().startswith("aprovado")

