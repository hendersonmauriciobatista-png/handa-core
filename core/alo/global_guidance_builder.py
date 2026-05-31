from datetime import datetime, timezone
from typing import Any, Dict

from core.alo.global_guidance_models import ALOGlobalGuidance, MacroLeaderSnapshot


class ALOGlobalGuidanceBuilder:
    """
    Construtor read-only do snapshot global do ALO.
    Macro Leaders entram apenas como sensores contextuais.
    """

    MACRO_LEADERS = ("BTCUSDC", "ETHUSDC", "BNBUSDC")

    def build(
        self,
        symbol: str,
        cycle_id: str,
        macro_index_snapshot: Dict[str, Any] | None = None,
    ) -> ALOGlobalGuidance:
        macro_index_snapshot = macro_index_snapshot or {}
        leaders = self._extract_macro_leaders(macro_index_snapshot)

        btc = leaders.get("BTCUSDC", MacroLeaderSnapshot("BTCUSDC"))
        eth = leaders.get("ETHUSDC", MacroLeaderSnapshot("ETHUSDC"))
        bnb = leaders.get("BNBUSDC", MacroLeaderSnapshot("BNBUSDC"))

        macro_alignment = float(macro_index_snapshot.get("macro_alignment", 0.0) or 0.0)
        macro_state = str(
            macro_index_snapshot.get("macro_state", "UNKNOWN") or "UNKNOWN"
        ).upper()
        macro_mode = str(
            macro_index_snapshot.get("mode", "PASSIVE_OBSERVER") or "PASSIVE_OBSERVER"
        ).upper()

        reason_codes = self._build_macro_reason_codes(
            macro_alignment, macro_state, leaders
        )
        explainability = (
            f"Macro Leaders READ_ONLY | alignment={macro_alignment:.4f} | "
            f"state={macro_state} | mode={macro_mode} | "
            f"btc={btc.trend}/{btc.momentum} | "
            f"eth={eth.trend}/{eth.momentum} | "
            f"bnb={bnb.trend}/{bnb.momentum}"
        )

        guidance = ALOGlobalGuidance(
            symbol=str(symbol or "").upper(),
            cycle_id=str(cycle_id or ""),
            timestamp=datetime.now(timezone.utc).isoformat(),
            macro_alignment=macro_alignment,
            macro_state=macro_state,
            macro_mode=macro_mode,
            btc_trend=btc.trend,
            eth_trend=eth.trend,
            bnb_trend=bnb.trend,
            btc_momentum=btc.momentum,
            eth_momentum=eth.momentum,
            bnb_momentum=bnb.momentum,
            btc_market_state=btc.market_state,
            eth_market_state=eth.market_state,
            bnb_market_state=bnb.market_state,
            btc_volume_ratio=btc.volume_ratio,
            eth_volume_ratio=eth.volume_ratio,
            bnb_volume_ratio=bnb.volume_ratio,
            macro_reason_codes=tuple(reason_codes),
            macro_explainability=explainability,
            operational_effect_count=0,
        )

        print(
            f"[MACRO LEADERS GUIDANCE] symbol={guidance.symbol} | "
            f"alignment={guidance.macro_alignment:.4f} | state={guidance.macro_state} | "
            f"btc={guidance.btc_trend}/{guidance.btc_momentum} | "
            f"eth={guidance.eth_trend}/{guidance.eth_momentum} | "
            f"bnb={guidance.bnb_trend}/{guidance.bnb_momentum}"
        )
        print(f"[ALO GLOBAL MACRO INPUT] {guidance.macro_explainability}")
        print("[ALO GLOBAL READONLY] no_effect=true | operational_effect_count=0")

        return guidance

    def _extract_macro_leaders(
        self, macro_index_snapshot: Dict[str, Any]
    ) -> Dict[str, MacroLeaderSnapshot]:
        leaders = {}
        for item in macro_index_snapshot.get("symbols", []) or []:
            symbol = str(item.get("symbol", "") or "").upper()
            if symbol not in self.MACRO_LEADERS:
                continue
            leaders[symbol] = MacroLeaderSnapshot(
                symbol=symbol,
                trend=self._normalize(item.get("trend")),
                momentum=self._normalize(item.get("momentum")),
                market_state=self._normalize(item.get("market_state")),
                volume_ratio=float(item.get("volume_ratio", 0.0) or 0.0),
            )
        return leaders

    def _normalize(self, value: Any) -> str:
        raw = str(value or "UNKNOWN").strip().upper()
        return raw.split(".")[-1] if "." in raw else raw

    def _build_macro_reason_codes(
        self,
        alignment: float,
        state: str,
        leaders: Dict[str, MacroLeaderSnapshot],
    ) -> list[str]:
        codes = [f"MACRO_STATE={state}", f"MACRO_ALIGNMENT={alignment:.4f}"]
        for symbol in self.MACRO_LEADERS:
            leader = leaders.get(symbol)
            if leader:
                codes.append(f"{symbol}_TREND={leader.trend}")
                codes.append(f"{symbol}_MOMENTUM={leader.momentum}")
        return codes
