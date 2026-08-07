class Logger:
    """
    Logger simples como subscriber do EventBus.
    """

    def on_slot_state(self, payload):
        print(f"[LOGGER][SLOT_STATE] Slot {payload['slot']} -> {payload['state']}")

    def on_signal(self, payload):
        print(f"[LOGGER][SIGNAL] Slot {payload['slot']} -> {payload['signal']}")

    def on_risk(self, payload):
        print(f"[LOGGER][RISK] Slot {payload['slot']} -> approved={payload['approved']}")

    def on_execution(self, payload):
        print(f"[LOGGER][EXECUTION] Slot {payload['slot']} -> {payload['result']}")
