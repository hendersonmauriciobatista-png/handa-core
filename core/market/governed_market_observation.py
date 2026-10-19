"""Authority-neutral market provenance captured from real source observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Iterable, Mapping, Optional

from core.execution.authority_digest import canonical_decimal, canonical_timestamp, sha256_digest


PRICE_TECHNICAL = "PRICE_TECHNICAL"
SELECTION_RADAR = "SELECTION_RADAR"
MARKET_CONTEXT = "MARKET_CONTEXT"
CLOSED = "CLOSED"
CLOSED_UNPROVEN = "CLOSED_UNPROVEN"
OPEN = "OPEN"
PROVENANCE_INCOMPLETE = "PROVENANCE_INCOMPLETE"
MARKET_OBSERVATION_CONSTITUENT = "MARKET_OBSERVATION_CONSTITUENT"
CAUSAL_DERIVED_CONSTITUENT = "CAUSAL_DERIVED_CONSTITUENT"


class ObservationDigest(str):
    """String digest carrying the proof metadata used to create it."""

    def __new__(
        cls,
        value: str,
        *,
        close_time: Optional[datetime] = None,
        close_status: Optional[str] = None,
        server_time_at: Optional[datetime] = None,
    ):
        result = str.__new__(cls, value)
        result.close_time = close_time
        result.close_status = close_status
        result.server_time_at = server_time_at
        return result


class BinanceServerTimeUnavailable(RuntimeError):
    """Raised when Binance server time cannot establish candle closure."""


def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc)
    raise TypeError("timestamp must be datetime or epoch milliseconds")


def server_time_provider(client: Any) -> datetime:
    """Read verified Binance server time from the existing client capability."""

    try:
        response = client.get_server_time()
        value = response.get("serverTime") if isinstance(response, Mapping) else None
        if value is None:
            raise BinanceServerTimeUnavailable("Binance server time is missing")
        return _utc(value)
    except BinanceServerTimeUnavailable:
        raise
    except Exception as exc:
        raise BinanceServerTimeUnavailable("Binance server time is unavailable") from exc


def _kline_value(kline: Any, index: int, name: str) -> Any:
    if not isinstance(kline, (list, tuple)) or len(kline) <= index:
        raise ValueError(f"kline {name} is missing")
    return kline[index]


@dataclass(frozen=True)
class GovernedKlineObservation:
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    close_price: Decimal
    close_status: str
    source_observation_at: datetime
    server_time_at: Optional[datetime] = None

    @property
    def is_closed(self) -> bool:
        return self.close_status == CLOSED

    @property
    def canonical_digest(self) -> str:
        digest = sha256_digest(
            {
                "symbol": self.symbol,
                "interval": self.interval,
                "open_time": self.open_time,
                "close_time": self.close_time,
                "close_price": canonical_decimal(self.close_price),
                "close_status": self.close_status,
                "source_observation_at": self.source_observation_at,
                "server_time_at": self.server_time_at,
            }
        )
        return ObservationDigest(
            digest,
            close_time=self.close_time,
            close_status=self.close_status,
            server_time_at=self.server_time_at,
        )


def capture_kline_observation(
    kline: Any,
    *,
    symbol: str = "",
    interval: str = "",
    server_time: Optional[datetime] = None,
    server_time_provider: Optional[Callable[[], datetime]] = None,
) -> GovernedKlineObservation:
    """Capture kline close semantics without using the local application clock."""

    open_time = _utc(_kline_value(kline, 0, "open_time"))
    close_time = _utc(_kline_value(kline, 6, "close_time"))
    close_price = Decimal(str(_kline_value(kline, 4, "close_price")))
    verified_server_time = server_time
    if verified_server_time is None and server_time_provider is not None:
        try:
            verified_server_time = server_time_provider()
        except Exception:
            verified_server_time = None
    if verified_server_time is not None:
        verified_server_time = _utc(verified_server_time)
        close_status = CLOSED if close_time < verified_server_time else OPEN
    else:
        close_status = CLOSED_UNPROVEN
    return GovernedKlineObservation(
        symbol=str(symbol or "").strip().upper(),
        interval=str(interval or "").strip(),
        open_time=open_time,
        close_time=close_time,
        close_price=close_price,
        close_status=close_status,
        source_observation_at=close_time,
        server_time_at=verified_server_time,
    )


@dataclass(frozen=True)
class TickerObservation:
    ticker_value: Decimal
    application_receipt_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker_value", Decimal(str(self.ticker_value)))
        object.__setattr__(self, "application_receipt_at", _utc(self.application_receipt_at))


@dataclass(frozen=True)
class MarketObservationConstituent:
    constituent_id: str
    source: str
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    close_status: str
    verified_server_time: Optional[datetime]
    semantic_digest: str = ""
    constituent_kind: str = MARKET_OBSERVATION_CONSTITUENT

    def __post_init__(self) -> None:
        open_time = _utc(self.open_time)
        close_time = _utc(self.close_time)
        server_time = _utc(self.verified_server_time) if self.verified_server_time else None
        object.__setattr__(self, "symbol", str(self.symbol).strip().upper())
        object.__setattr__(self, "interval", str(self.interval).strip())
        object.__setattr__(self, "open_time", open_time)
        object.__setattr__(self, "close_time", close_time)
        object.__setattr__(self, "verified_server_time", server_time)
        if not self.semantic_digest:
            object.__setattr__(
                self,
                "semantic_digest",
                sha256_digest(
                    {
                        "constituent_kind": self.constituent_kind,
                        "constituent_id": self.constituent_id,
                        "source": self.source,
                        "symbol": self.symbol,
                        "interval": self.interval,
                        "open_time": self.open_time,
                        "close_time": self.close_time,
                        "close_status": self.close_status,
                        "verified_server_time": self.verified_server_time,
                    }
                ),
            )

    def as_record(self) -> dict[str, Any]:
        return {
            "constituent_kind": self.constituent_kind,
            "constituent_id": self.constituent_id,
            "source": self.source,
            "symbol": self.symbol,
            "interval": self.interval,
            "open_time": self.open_time,
            "close_time": self.close_time,
            "close_status": self.close_status,
            "verified_server_time": self.verified_server_time,
            "semantic_digest": self.semantic_digest,
            "trustworthy_market_time": self.close_status == CLOSED,
        }


@dataclass(frozen=True)
class CausalDerivedConstituent:
    constituent_id: str
    source: str
    symbol: str
    semantic_digest: str = ""
    application_receipt_at: Optional[datetime] = None
    causal_capture_time: Optional[datetime] = None
    upstream_market_observation_ids: tuple[str, ...] = ()
    constituent_kind: str = CAUSAL_DERIVED_CONSTITUENT

    def __post_init__(self) -> None:
        receipt = _utc(self.application_receipt_at) if self.application_receipt_at else None
        capture = _utc(self.causal_capture_time) if self.causal_capture_time else None
        object.__setattr__(self, "symbol", str(self.symbol).strip().upper())
        object.__setattr__(self, "application_receipt_at", receipt)
        object.__setattr__(self, "causal_capture_time", capture)
        object.__setattr__(
            self,
            "upstream_market_observation_ids",
            tuple(sorted(str(item) for item in self.upstream_market_observation_ids)),
        )
        if not self.semantic_digest:
            object.__setattr__(
                self,
                "semantic_digest",
                sha256_digest(
                    {
                        "constituent_kind": self.constituent_kind,
                        "constituent_id": self.constituent_id,
                        "source": self.source,
                        "symbol": self.symbol,
                        "application_receipt_at": self.application_receipt_at,
                        "causal_capture_time": self.causal_capture_time,
                        "upstream_market_observation_ids": self.upstream_market_observation_ids,
                    }
                ),
            )

    def as_record(self) -> dict[str, Any]:
        return {
            "constituent_kind": self.constituent_kind,
            "constituent_id": self.constituent_id,
            "source": self.source,
            "symbol": self.symbol,
            "semantic_digest": self.semantic_digest,
            "application_receipt_at": self.application_receipt_at,
            "causal_capture_time": self.causal_capture_time,
            "upstream_market_observation_ids": self.upstream_market_observation_ids,
            "trustworthy_market_time": False,
        }


def kline_constituent(observation: GovernedKlineObservation) -> MarketObservationConstituent:
    constituent_id = (
        f"binance:kline:{observation.symbol}:{observation.interval}:"
        f"{observation.open_time.isoformat()}:{observation.close_time.isoformat()}"
    )
    return MarketObservationConstituent(
        constituent_id=constituent_id,
        source="binance:kline",
        symbol=observation.symbol,
        interval=observation.interval,
        open_time=observation.open_time,
        close_time=observation.close_time,
        close_status=observation.close_status,
        verified_server_time=observation.server_time_at,
        semantic_digest=observation.canonical_digest,
    )


def ticker_constituent(
    *, symbol: str, ticker_value: Any, application_receipt_at: datetime
) -> CausalDerivedConstituent:
    receipt = _utc(application_receipt_at)
    value = Decimal(str(ticker_value))
    digest = sha256_digest(
        {
            "constituent_kind": CAUSAL_DERIVED_CONSTITUENT,
            "source": "binance:ticker",
            "symbol": str(symbol).strip().upper(),
            "ticker_value": canonical_decimal(value),
            "ticker_application_receipt_at": receipt,
        }
    )
    return CausalDerivedConstituent(
        constituent_id=f"binance:ticker:{str(symbol).strip().upper()}:{digest}",
        source="binance:ticker",
        symbol=symbol,
        semantic_digest=digest,
        application_receipt_at=receipt,
        causal_capture_time=receipt,
    )


def canonical_group_digest(
    *,
    group_type: str,
    group_identity: str,
    constituents: Iterable[Mapping[str, Any]],
    market_oldest: Optional[datetime],
    market_newest: Optional[datetime],
    missing_evidence: Iterable[str] = (),
    trust_class: str = "UNTRUSTED",
) -> str:
    canonical_constituents = tuple(
        sorted(
            (dict(item) for item in constituents),
            key=lambda item: str(item.get("constituent_id", "")),
        )
    )
    return sha256_digest(
        {
            "group_type": group_type,
            "group_identity": group_identity,
            "constituents": canonical_constituents,
            "market_oldest": market_oldest,
            "market_newest": market_newest,
            "missing_evidence": tuple(sorted(str(item) for item in missing_evidence)),
            "trust_class": trust_class,
        }
    )


@dataclass(frozen=True)
class ObservationGroup:
    group_type: str
    source_identities: tuple[str, ...] = ()
    constituent_observation_times: tuple[datetime, ...] = ()
    oldest_observation_at: Optional[datetime] = None
    newest_observation_at: Optional[datetime] = None
    canonical_digest: str = ""
    completeness: str = "COMPLETE"
    constituent_observation_digests: tuple[str, ...] = ()
    constituent_closure_statuses: tuple[str, ...] = ()
    verified_server_times: tuple[datetime, ...] = ()
    group_identity: str = ""
    constituents: tuple[Mapping[str, Any], ...] = ()
    missing_evidence: tuple[str, ...] = ()
    trust_class: str = "UNTRUSTED"

    def __post_init__(self) -> None:
        identities = tuple(sorted(str(item) for item in self.source_identities))
        times = tuple(_utc(item) for item in self.constituent_observation_times if item is not None)
        digests = tuple(str(item) for item in self.constituent_observation_digests)
        statuses = tuple(str(item) for item in self.constituent_closure_statuses)
        server_times = tuple(_utc(item) for item in self.verified_server_times if item is not None)
        constituents = tuple(dict(item) for item in self.constituents)
        group_identity = self.group_identity or f"{self.group_type}:group"
        missing_evidence = tuple(sorted(str(item) for item in self.missing_evidence))
        oldest = min(times) if times else self.oldest_observation_at
        newest = max(times) if times else self.newest_observation_at
        if oldest is not None:
            oldest = _utc(oldest)
        if newest is not None:
            newest = _utc(newest)
        completeness = self.completeness
        if not times or oldest is None or newest is None:
            completeness = PROVENANCE_INCOMPLETE
        digest = self.canonical_digest or canonical_group_digest(
            group_type=self.group_type,
            group_identity=group_identity,
            constituents=constituents,
            market_oldest=oldest,
            market_newest=newest,
            missing_evidence=missing_evidence,
            trust_class=self.trust_class,
        )
        object.__setattr__(self, "source_identities", identities)
        object.__setattr__(self, "constituent_observation_times", times)
        object.__setattr__(self, "oldest_observation_at", oldest)
        object.__setattr__(self, "newest_observation_at", newest)
        object.__setattr__(self, "canonical_digest", digest)
        object.__setattr__(self, "completeness", completeness)
        object.__setattr__(self, "constituent_observation_digests", digests)
        object.__setattr__(self, "constituent_closure_statuses", statuses)
        object.__setattr__(self, "verified_server_times", server_times)
        object.__setattr__(self, "group_identity", group_identity)
        object.__setattr__(self, "constituents", constituents)
        object.__setattr__(self, "missing_evidence", missing_evidence)
        object.__setattr__(self, "trust_class", str(self.trust_class))


def build_observation_group(
    group_type: str,
    *,
    source_identities: Iterable[str] = (),
    observation_times: Iterable[datetime] = (),
    observation_digests: Iterable[str] = (),
    closure_statuses: Iterable[str] = (),
    verified_server_times: Iterable[datetime] = (),
    group_identity: str = "",
    constituents: Iterable[Mapping[str, Any]] = (),
    missing_evidence: Iterable[str] = (),
    trust_class: str = "UNTRUSTED",
) -> ObservationGroup:
    return ObservationGroup(
        group_type=str(group_type),
        source_identities=tuple(source_identities),
        constituent_observation_times=tuple(observation_times),
        constituent_observation_digests=tuple(observation_digests),
        constituent_closure_statuses=tuple(closure_statuses),
        verified_server_times=tuple(verified_server_times),
        group_identity=group_identity,
        constituents=tuple(constituents),
        missing_evidence=tuple(missing_evidence),
        trust_class=str(trust_class),
    )


def append_ticker_constituent(
    provenance: Mapping[str, Any],
    *,
    symbol: str,
    ticker_observation: TickerObservation,
) -> dict[str, Any]:
    """Add the decision-time ticker without changing candle provenance."""

    result = {str(key): value for key, value in (provenance or {}).items()}
    digests = {
        str(key): tuple(value) if isinstance(value, (list, tuple)) else value
        for key, value in dict(result.get("source_group_constituent_digests", {})).items()
    }
    constituents = {
        str(key): list(value) if isinstance(value, (list, tuple)) else []
        for key, value in dict(result.get("source_group_constituents", {})).items()
    }
    ticker = ticker_constituent(
        symbol=symbol,
        ticker_value=ticker_observation.ticker_value,
        application_receipt_at=ticker_observation.application_receipt_at,
    )
    ticker_record = ticker.as_record()
    price_constituents = constituents.setdefault(PRICE_TECHNICAL, [])
    if not any(
        str(item.get("semantic_digest", "")) == ticker.semantic_digest
        for item in price_constituents
        if isinstance(item, Mapping)
    ):
        price_constituents.append(ticker_record)
    price_digests = list(digests.get(PRICE_TECHNICAL, ()))
    if ticker.semantic_digest not in price_digests:
        price_digests.append(ticker.semantic_digest)
    digests[PRICE_TECHNICAL] = tuple(price_digests)
    result["source_group_constituent_digests"] = digests
    result["source_group_constituents"] = constituents
    result.setdefault("source_group_identities", {})
    result["source_group_identities"].setdefault(
        PRICE_TECHNICAL, f"{PRICE_TECHNICAL}:{str(symbol).strip().upper()}"
    )
    intervals = dict(result.get("source_group_intervals", {}))
    interval = intervals.get(PRICE_TECHNICAL)
    oldest = newest = None
    if isinstance(interval, Mapping):
        oldest, newest = interval.get("oldest"), interval.get("newest")
    elif interval is not None:
        oldest = newest = interval
    result.setdefault("source_group_missing_evidence", {})
    result.setdefault("source_group_trust", {})
    result["source_group_digests"] = dict(result.get("source_group_digests", {}))
    result["source_group_digests"][PRICE_TECHNICAL] = canonical_group_digest(
        group_type=PRICE_TECHNICAL,
        group_identity=result["source_group_identities"][PRICE_TECHNICAL],
        constituents=price_constituents,
        market_oldest=oldest,
        market_newest=newest,
        missing_evidence=result["source_group_missing_evidence"].get(PRICE_TECHNICAL, ()),
        trust_class=result["source_group_trust"].get(PRICE_TECHNICAL, "UNTRUSTED"),
    )
    return result


def group_closure_status(observations: Iterable[Any]) -> str:
    """Return the strongest closure status supported by all observations."""

    statuses = tuple(str(getattr(item, "close_status", "")) for item in observations)
    if not statuses:
        return PROVENANCE_INCOMPLETE
    if any(status == CLOSED_UNPROVEN for status in statuses):
        return CLOSED_UNPROVEN
    if any(status == OPEN for status in statuses):
        return OPEN
    if all(status == CLOSED for status in statuses):
        return CLOSED
    return PROVENANCE_INCOMPLETE


def source_observation_at(observation: Any) -> Optional[datetime]:
    value = getattr(observation, "source_observation_at", None)
    return _utc(value) if value is not None else None


def application_receipt_at(observation: Any) -> Optional[datetime]:
    value = getattr(observation, "application_receipt_at", None)
    return _utc(value) if value is not None else None
