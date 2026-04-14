import time
from dataclasses import dataclass


# =====================================================
# MODELOS DE MÉTRICA
# =====================================================

@dataclass(frozen=True)
class MetricValue:
    """
    Representa uma métrica normalizada (0–100)
    """
    value: int          # 0–100
    label: str          # texto humano
    level: str          # INFO | OK | WARN | CRITICAL


# =====================================================
# SYSTEM METRICS (MOCK)
# =====================================================

class SystemMetrics:
    """
    Calcula métricas do sistema H&A.
    Neste estágio:
    - valores MOCKADOS
    - coerentes
    - estáveis
    """

    def __init__(self):
        self._last_tick = time.time()

    # -------------------------
    # ATIVIDADE DO H&A
    # -------------------------

    def activity(self) -> MetricValue:
        """
        Atividade do sistema (0–100)
        MOCK: baseado em tempo de execução.
        """

        uptime = time.time() - self._last_tick

        # Mock simples e coerente
        if uptime < 5:
            value = 15
        elif uptime < 15:
            value = 35
        elif uptime < 30:
            value = 60
        else:
            value = 75

        return MetricValue(
            value=value,
            label=f"{value}%",
            level=self._activity_level(value)
        )

    def _activity_level(self, value: int) -> str:
        if value < 20:
            return "INFO"
        if value < 50:
            return "OK"
        if value < 80:
            return "NORMAL"
        return "HIGH"

    # -------------------------
    # LATÊNCIA DO SISTEMA
    # -------------------------

    def latency(self) -> MetricValue:
        """
        Latência do sistema (0–100)
        MOCK: simula latência interna em ms
        """

        # Simulação fixa (por enquanto)
        simulated_ms = 180

        value = self._normalize_latency(simulated_ms)

        return MetricValue(
            value=value,
            label=f"{value}%",
            level=self._latency_level(value)
        )

    def _normalize_latency(self, ms: int) -> int:
        """
        Converte ms em nota 0–100
        (quanto menor ms, maior a nota)
        """
        if ms <= 100:
            return 100
        if ms <= 200:
            return 80
        if ms <= 400:
            return 60
        if ms <= 700:
            return 40
        if ms <= 1000:
            return 20
        return 10

    def _latency_level(self, value: int) -> str:
        if value >= 80:
            return "EXCELLENT"
        if value >= 50:
            return "NORMAL"
        if value >= 20:
            return "WARN"
        return "CRITICAL"
