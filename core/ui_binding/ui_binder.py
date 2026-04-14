# core/ui_binding/ui_binder.py

class UIBinder:
    """
    Conecta o StateStore à UI.
    """

    def __init__(self, store, renderer):
        self.store = store
        self.renderer = renderer
        self.store.subscribe(self.on_state_change)

    def on_state_change(self, state_snapshot: dict):
        ui_payload = self.map_state_to_ui(state_snapshot)
        self.renderer.render(ui_payload)

    def map_state_to_ui(self, state: dict) -> dict:
        payload = {}

        # global
        if "system_status" in state:
            payload["system_status"] = state["system_status"]

        # slots
        for k, v in state.items():
            if k.startswith("slot_"):
                payload[k] = v

        return payload
