# logging_ui/event_model.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class UIEvent:
    timestamp_utc: datetime
    event_type: str
    origin: str
    slot_id: Optional[str]
    prev_state: Optional[str]
    current_state: str
    reason_code: Optional[str] = None
