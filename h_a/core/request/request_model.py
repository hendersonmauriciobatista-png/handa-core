from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict, Optional

from h_a.core.request.request_types import RequestType, RequestStatus


@dataclass(frozen=True)
class Request:
    request_id: str = field(default_factory=lambda: str(uuid4()))
    type: RequestType = RequestType.REQUEST_SET_UI_MODE
    origin: str = "UI"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    system_phase: str = "FASE_3_1"
    payload: Dict = field(default_factory=dict)
    status: RequestStatus = RequestStatus.PENDING
    decision_reason: Optional[str] = None
