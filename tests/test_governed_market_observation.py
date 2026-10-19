"""Expected-RED contracts for the 2B8B governed market observation layer."""

from importlib import import_module
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.market.governed_market_observation import PRICE_TECHNICAL


def _observation_contract():
    try:
        return import_module("core.market.governed_market_observation")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "EXPECTED_CONTRACT_RED::governed market observation module is missing; "
            f"missing={exc.name}"
        )


def test_kline_contract_uses_close_time_and_explicit_closed_status():
    module = _observation_contract()

    assert hasattr(module, "GovernedKlineObservation")
    assert hasattr(module, "CLOSED")
    assert hasattr(module, "CLOSED_UNPROVEN")
    assert hasattr(module, "capture_kline_observation")


def test_closed_candle_contract_requires_injectable_binance_server_time():
    module = _observation_contract()

    assert hasattr(module, "BinanceServerTimeUnavailable")
    assert hasattr(module, "server_time_provider")
    assert "server_time" in getattr(module, "capture_kline_observation").__annotations__


def test_ticker_contract_preserves_value_and_receipt_timestamp_separately():
    module = _observation_contract()

    assert hasattr(module, "TickerObservation")
    fields = getattr(module, "TickerObservation").__dataclass_fields__
    assert "ticker_value" in fields
    assert "application_receipt_at" in fields
    assert "candle_close_time" not in fields or "ticker_value" in fields


def test_multi_source_contract_keeps_required_groups_and_intervals():
    module = _observation_contract()

    assert hasattr(module, "PRICE_TECHNICAL")
    assert hasattr(module, "SELECTION_RADAR")
    assert hasattr(module, "MARKET_CONTEXT")
    assert hasattr(module, "ObservationGroup")
    group_fields = getattr(module, "ObservationGroup").__dataclass_fields__
    for field_name in (
        "source_identities",
        "oldest_observation_at",
        "newest_observation_at",
        "canonical_digest",
    ):
        assert field_name in group_fields


def test_missing_source_timestamp_is_incomplete_without_local_clock_fallback():
    module = _observation_contract()

    assert hasattr(module, "PROVENANCE_INCOMPLETE")
    assert hasattr(module, "build_observation_group")


def test_cached_source_age_is_preserved_by_observation_contract():
    module = _observation_contract()

    assert hasattr(module, "source_observation_at")
    assert hasattr(module, "application_receipt_at")
    assert getattr(module, "source_observation_at") is not getattr(
        module, "application_receipt_at"
    )


def _kline(*, open_time, close_time, close_price="100.25"):
    return [
        open_time,
        "99.0",
        "101.0",
        "98.0",
        close_price,
        "12.5",
        close_time,
        "0",
        "0",
        "0",
        "0",
        "0",
    ]


def test_kline_close_proof_uses_index_six_and_strict_verified_server_time():
    module = _observation_contract()
    verified_server_time = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)

    observation = module.capture_kline_observation(
        _kline(
            open_time=datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc),
            close_time=datetime(2026, 1, 1, 0, 4, tzinfo=timezone.utc),
        ),
        symbol="HYPEUSDC",
        interval="1m",
        server_time=verified_server_time,
    )

    assert observation.close_time == datetime(2026, 1, 1, 0, 4, tzinfo=timezone.utc)
    assert observation.source_observation_at == observation.close_time
    assert observation.close_status == module.CLOSED

    equal_boundary = module.capture_kline_observation(
        _kline(
            open_time=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
            close_time=verified_server_time,
        ),
        server_time=verified_server_time,
    )
    assert equal_boundary.close_status == module.OPEN


def test_server_time_failure_is_closed_unproven_and_local_clock_cannot_upgrade_it():
    module = _observation_contract()

    def unavailable_server_time():
        raise module.BinanceServerTimeUnavailable("server time unavailable")

    observation = module.capture_kline_observation(
        _kline(
            open_time=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            close_time=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        ),
        server_time_provider=unavailable_server_time,
    )

    assert observation.close_status == module.CLOSED_UNPROVEN
    assert not observation.is_closed
    assert observation.server_time_at is None


def test_group_age_is_derived_from_each_constituent_observation_not_receipt_time():
    module = _observation_contract()
    source_times = (
        datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 0, 4, tzinfo=timezone.utc),
    )
    group = module.build_observation_group(
        module.SELECTION_RADAR,
        source_identities=("radar-a", "radar-b"),
        observation_times=source_times,
    )

    assert group.oldest_observation_at == source_times[0]
    assert group.newest_observation_at == source_times[1]
    assert group.constituent_observation_times == source_times
    assert group.canonical_digest


def test_multisource_group_intervals_are_isolated_from_price_changes():
    module = _observation_contract()
    price_times = (
        datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
    )
    radar_times = (
        datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 0, 6, tzinfo=timezone.utc),
    )
    context_times = (
        datetime(2026, 1, 1, 0, 9, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc),
    )
    price = module.build_observation_group(
        module.PRICE_TECHNICAL,
        source_identities=("kline-a", "kline-b"),
        observation_times=price_times,
    )
    radar = module.build_observation_group(
        module.SELECTION_RADAR,
        source_identities=("radar-a", "radar-b"),
        observation_times=radar_times,
    )
    context = module.build_observation_group(
        module.MARKET_CONTEXT,
        source_identities=("context-a", "context-b"),
        observation_times=context_times,
    )

    assert price.oldest_observation_at == price_times[0]
    assert price.newest_observation_at == price_times[1]
    assert radar.oldest_observation_at == radar_times[0]
    assert radar.newest_observation_at == radar_times[1]
    assert context.oldest_observation_at == context_times[0]
    assert context.newest_observation_at == context_times[1]
    assert radar.oldest_observation_at != price.oldest_observation_at
    assert context.oldest_observation_at != price.oldest_observation_at

    changed_price = module.build_observation_group(
        module.PRICE_TECHNICAL,
        source_identities=("kline-new-a", "kline-new-b"),
        observation_times=(
            datetime(2026, 1, 1, 0, 20, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 0, 21, tzinfo=timezone.utc),
        ),
    )
    assert changed_price.oldest_observation_at != radar.oldest_observation_at
    assert changed_price.oldest_observation_at != context.oldest_observation_at
    assert radar.oldest_observation_at == radar_times[0]
    assert context.oldest_observation_at == context_times[0]


def test_real_scanner_to_slot_path_carries_kline_and_decision_ticker_as_mixed_group():
    """The live pre-decision path must retain both causal constituents."""

    from core.scanner.technical_scanner import TechnicalScanner
    from core.slot_controller import SlotController

    class BinanceClient:
        def get_klines(self, *, symbol, interval, limit):
            base = datetime(2026, 1, 1, tzinfo=timezone.utc)
            return [
                _kline(
                    open_time=(base.timestamp() + index * 60) * 1000,
                    close_time=(base.timestamp() + (index + 1) * 60 - 1) * 1000,
                    close_price=str(100 + index * 0.01),
                )
                for index in range(limit)
            ]

        def get_server_time(self):
            return {"serverTime": datetime(2026, 1, 1, 2, tzinfo=timezone.utc)}

        def get_symbol_ticker(self, *, symbol):
            return {"price": "101.25"}

    client = BinanceClient()
    opportunity = TechnicalScanner(client).analyze_symbol(
        "HYPEUSDC", interval="1m", limit=100
    )
    snapshot = SlotController([], client=client)._build_snapshot_from_opportunity(
        opportunity
    )

    assert snapshot.price == Decimal("101.25"), (
        "EXPECTED_CONTRACT_RED::ticker value consumed by DecisionEngine changed"
    )
    provenance = getattr(snapshot, "_governed_provenance")
    constituents = provenance["source_group_constituent_digests"][PRICE_TECHNICAL]
    assert len(constituents) >= 2, (
        "EXPECTED_CONTRACT_RED::PRICE_TECHNICAL missing DECISION_TICKER constituent"
    )
