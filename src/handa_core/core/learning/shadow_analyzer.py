# ============================================================
# core/learning/shadow_analyzer.py
# LC-3 — Shadow Learning Analyzer
# Analyzer oficial v1.0
# ============================================================

from typing import Dict, List, Optional

from core.learning.models import (
    TradeLearningSample,
    PatternStats,
    ShadowAnalysisReport,
)


class ShadowLearningAnalyzer:
    """
    Analyzer observador do LC-3.

    Responsabilidades:
    - transformar histórico bruto em samples estruturados
    - agrupar trades por padrões simples
    - calcular estatísticas por padrão
    - gerar relatório final observador
    """

    def _to_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _safe_str(self, value, default: str = "") -> str:
        if value is None:
            return default

        try:
            if hasattr(value, "value"):
                return str(value.value).strip()
            return str(value).strip()
        except Exception:
            return default

    def _safe_upper(self, value, default: str = "") -> str:
        return self._safe_str(value, default=default).upper()

    def _build_sample_from_position(self, pos) -> TradeLearningSample:
        opened_at = ""
        closed_at = ""
        duration_seconds = 0

        try:
            if getattr(pos, "opened_at", None):
                opened_at = pos.opened_at.isoformat()
            if getattr(pos, "closed_at", None):
                closed_at = pos.closed_at.isoformat()

            if getattr(pos, "opened_at", None) and getattr(pos, "closed_at", None):
                duration_seconds = int((pos.closed_at - pos.opened_at).total_seconds())
        except Exception:
            duration_seconds = 0

        pnl_usdc = self._to_float(getattr(pos, "net_pnl_usdc", 0.0), default=0.0)
        pnl_pct = self._to_float(getattr(pos, "net_pnl_pct", 0.0), default=0.0)

        sample = TradeLearningSample(
            symbol=self._safe_upper(getattr(pos, "symbol", "")),
            entry_price=self._to_float(getattr(pos, "entry_price", 0.0), default=0.0),
            exit_price=self._to_float(getattr(pos, "exit_price", 0.0), default=0.0),
            pnl_usdc=pnl_usdc,
            pnl_pct=pnl_pct,
            duration_seconds=duration_seconds,
            close_reason=self._safe_upper(getattr(pos, "close_reason", "")),
            opened_at=opened_at,
            closed_at=closed_at,
            is_win=pnl_usdc > 0,
            is_loss=pnl_usdc < 0,
            context={},
        )

        return sample

    def _build_pattern_key(self, sample: TradeLearningSample) -> str:
        """
        Padrão inicial simples e seguro.

        v1.0:
        - symbol
        - close_reason

        Depois podemos enriquecer com:
        - MQII state
        - regime de mercado
        - faixa de duração
        - classe de volatilidade
        """
        symbol = self._safe_upper(sample.symbol, default="UNKNOWN")
        close_reason = self._safe_upper(sample.close_reason, default="UNKNOWN")

        return f"{symbol}|{close_reason}"

    def _group_by_pattern(
        self, samples: List[TradeLearningSample]
    ) -> Dict[str, List[TradeLearningSample]]:
        grouped: Dict[str, List[TradeLearningSample]] = {}

        for sample in samples:
            pattern_key = self._build_pattern_key(sample)

            if pattern_key not in grouped:
                grouped[pattern_key] = []

            grouped[pattern_key].append(sample)

        return grouped

    def _build_pattern_stats(
        self,
        pattern_key: str,
        samples: List[TradeLearningSample],
    ) -> PatternStats:
        total_trades = len(samples)
        wins = sum(1 for s in samples if s.is_win)
        losses = sum(1 for s in samples if s.is_loss)

        total_pnl_usdc = sum(self._to_float(s.pnl_usdc, 0.0) for s in samples)
        total_pnl_pct = sum(self._to_float(s.pnl_pct, 0.0) for s in samples)
        total_duration = sum(int(s.duration_seconds or 0) for s in samples)

        win_rate = (wins / total_trades) if total_trades > 0 else 0.0
        avg_pnl_usdc = (total_pnl_usdc / total_trades) if total_trades > 0 else 0.0
        avg_pnl_pct = (total_pnl_pct / total_trades) if total_trades > 0 else 0.0
        avg_duration_seconds = (
            total_duration / total_trades if total_trades > 0 else 0.0
        )

        return PatternStats(
            pattern_key=pattern_key,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            win_rate=round(win_rate, 4),
            avg_pnl_usdc=round(avg_pnl_usdc, 4),
            avg_pnl_pct=round(avg_pnl_pct, 4),
            avg_duration_seconds=round(avg_duration_seconds, 2),
            samples=[s.to_dict() for s in samples],
        )

    def analyze_history(self, history: Optional[List]) -> ShadowAnalysisReport:
        history = history or []

        samples: List[TradeLearningSample] = []
        notes: List[str] = []

        for pos in history:
            try:
                sample = self._build_sample_from_position(pos)
                samples.append(sample)
            except Exception as e:
                notes.append(f"Falha ao converter posição em sample: {e}")

        total_samples = len(samples)
        wins = sum(1 for s in samples if s.is_win)
        losses = sum(1 for s in samples if s.is_loss)

        total_pnl_usdc = sum(self._to_float(s.pnl_usdc, 0.0) for s in samples)
        total_pnl_pct = sum(self._to_float(s.pnl_pct, 0.0) for s in samples)

        overall_win_rate = (wins / total_samples) if total_samples > 0 else 0.0
        overall_avg_pnl_usdc = (
            total_pnl_usdc / total_samples if total_samples > 0 else 0.0
        )
        overall_avg_pnl_pct = (
            total_pnl_pct / total_samples if total_samples > 0 else 0.0
        )

        grouped = self._group_by_pattern(samples)
        pattern_stats = [
            self._build_pattern_stats(pattern_key, grouped_samples)
            for pattern_key, grouped_samples in grouped.items()
        ]

        best_patterns = sorted(
            pattern_stats,
            key=lambda p: (p.win_rate, p.avg_pnl_usdc, p.total_trades),
            reverse=True,
        )[:5]

        worst_patterns = sorted(
            pattern_stats,
            key=lambda p: (p.win_rate, p.avg_pnl_usdc),
        )[:5]

        report = ShadowAnalysisReport(
            total_samples=total_samples,
            total_patterns=len(pattern_stats),
            wins=wins,
            losses=losses,
            overall_win_rate=round(overall_win_rate, 4),
            overall_avg_pnl_usdc=round(overall_avg_pnl_usdc, 4),
            overall_avg_pnl_pct=round(overall_avg_pnl_pct, 4),
            best_patterns=[p.to_dict() for p in best_patterns],
            worst_patterns=[p.to_dict() for p in worst_patterns],
            notes=notes,
        )

        if total_samples == 0:
            report.notes.append("Sem trades fechados suficientes para análise.")

        return report
