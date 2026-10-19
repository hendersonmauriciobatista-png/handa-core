# ============================================================
# core/scanner/technical_scanner.py
# Scanner técnico de tokens do H&A
# ============================================================

from core.market.market_snapshot_cache import MarketSnapshotCache
from core.market.market_data_to_indicators import MarketDataToIndicators
from core.sensors.sensor_hub import SensorHub
from core.market.governed_market_observation import (
    PRICE_TECHNICAL,
    build_observation_group,
    kline_constituent,
    capture_kline_observation,
    group_closure_status,
    server_time_provider,
)


class TechnicalScanner:

    def __init__(self, client):

        self.client = client
        self.cache = MarketSnapshotCache(client)


    def analyze_symbol(self, symbol, interval="5m", limit=100):
        """
        Analisa tecnicamente um único token
        """

        klines = self.cache.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit
        )

        snapshot = MarketDataToIndicators.build_snapshot_from_klines(
            klines
        )

        sensor_result = SensorHub.analyze(snapshot)

        observations = []
        for kline in klines[-1:]:
            observations.append(
                capture_kline_observation(
                    kline,
                    symbol=symbol,
                    interval=interval,
                    server_time_provider=lambda: server_time_provider(self.client),
                )
            )
        price_group = build_observation_group(
            PRICE_TECHNICAL,
            source_identities=(f"binance:kline:{symbol}:{interval}",),
            observation_times=tuple(
                observation.source_observation_at for observation in observations
            ),
            observation_digests=tuple(
                observation.canonical_digest for observation in observations
            ),
            closure_statuses=tuple(
                observation.close_status for observation in observations
            ),
            verified_server_times=tuple(
                observation.server_time_at
                for observation in observations
                if observation.server_time_at is not None
            ),
            group_identity=f"{PRICE_TECHNICAL}:{str(symbol).strip().upper()}:{interval}",
            constituents=tuple(
                kline_constituent(observation).as_record()
                for observation in observations
            ),
            trust_class=("TRUSTED_MARKET_TIME" if group_closure_status(observations) == "CLOSED" else "UNTRUSTED"),
        )
        server_times = tuple(
            observation.server_time_at
            for observation in observations
            if observation.server_time_at is not None
        )

        return {
            "symbol": symbol,
            "snapshot": snapshot,
            "analysis": sensor_result,
            "governed_provenance": {
                "source_group_timestamps": {
                    PRICE_TECHNICAL: price_group.newest_observation_at
                },
                "source_group_digests": {
                    PRICE_TECHNICAL: price_group.canonical_digest
                },
                "source_group_intervals": {
                    PRICE_TECHNICAL: {
                        "oldest": price_group.oldest_observation_at,
                        "newest": price_group.newest_observation_at,
                    }
                },
                "source_group_closure_statuses": {
                    PRICE_TECHNICAL: group_closure_status(observations),
                },
                "source_group_server_times": {
                    PRICE_TECHNICAL: server_times[0]
                    if len(server_times) == 1
                    else server_times,
                },
                "source_group_constituent_digests": {
                    PRICE_TECHNICAL: tuple(
                        observation.canonical_digest for observation in observations
                    ),
                },
                "source_group_identities": {
                    PRICE_TECHNICAL: price_group.group_identity,
                },
                "source_group_constituents": {
                    PRICE_TECHNICAL: price_group.constituents,
                },
                "source_group_missing_evidence": {
                    PRICE_TECHNICAL: price_group.missing_evidence,
                },
                "source_group_trust": {
                    PRICE_TECHNICAL: price_group.trust_class,
                },
                "price_technical_observations": tuple(observations),
            },
        }
