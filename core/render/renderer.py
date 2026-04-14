# core/render/renderer.py

class Renderer:
    """
    Aplica o payload visual na UI Tkinter.
    """

    def __init__(self, widgets: dict):
        self.widgets = widgets

    def render(self, ui_payload: dict):

        # --------- GLOBAL ---------
        if "system_status" in ui_payload and "system_label" in self.widgets:
            self.widgets["system_label"].config(
                text=ui_payload["system_status"]
            )

        # --------- SLOTS ---------
        if "slots" in self.widgets:
            slot_widgets = self.widgets["slots"]

            for key, value in ui_payload.items():
                if key.startswith("slot_") and key.endswith("_state"):
                    # key: slot_1_state
                    parts = key.split("_")
                    slot_id = int(parts[1])

                    if slot_id in slot_widgets:
                        w = slot_widgets[slot_id]
                        w["data"]["state"] = value
                        w["state_lbl"].config(text=value)

                if key.startswith("slot_") and key.endswith("_mode"):
                    parts = key.split("_")
                    slot_id = int(parts[1])

                    if slot_id in slot_widgets:
                        w = slot_widgets[slot_id]
                        w["data"]["mode"] = value
                        w["mode_lbl"].config(text=f"MODO: {value}")
