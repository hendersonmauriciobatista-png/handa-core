# test_logging_ui.py
from datetime import datetime
from logging_ui.event_model import UIEvent
from logging_ui.event_logger import EventLogger
from logging_ui.event_view import format_event

logger = EventLogger(max_events=3)

e1 = UIEvent(
    timestamp_utc=datetime.utcnow(),
    event_type="STATE_CHANGED",
    origin="SYSTEM",
    slot_id=None,
    prev_state="SYSTEM_READY",
    current_state="SYSTEM_RUNNING",
)

e2 = UIEvent(
    timestamp_utc=datetime.utcnow(),
    event_type="SLOT_UPDATE",
    origin="EXECUTOR",
    slot_id="S1",
    prev_state="READY",
    current_state="TRADING",
)

logger.log(e1)
logger.log(e2)

events = logger.get_recent()
assert len(events) == 2

text = format_event(events[0])
assert "STATE_CHANGED" in text
assert "SYSTEM_RUNNING" in text

print("✔ EventLogger OK")
print("✔ EventView OK")
print("🎉 BLOCO 4 VALIDADO COM SUCESSO")
