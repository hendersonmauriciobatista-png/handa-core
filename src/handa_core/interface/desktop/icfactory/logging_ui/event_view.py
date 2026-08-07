# logging_ui/event_view.py
from logging_ui.event_model import UIEvent


def format_event(event: UIEvent) -> str:
    """
    Converte evento em string legível para UI.
    """
    base = (
        f"[{event.timestamp_utc.isoformat()}] "
        f"{event.event_type} | "
        f"origin={event.origin} | "
        f"state={event.current_state}"
    )

    if event.slot_id:
        base += f" | slot={event.slot_id}"

    if event.reason_code:
        base += f" | reason={event.reason_code}"

    return base
