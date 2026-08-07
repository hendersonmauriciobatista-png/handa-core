from interface.desktop.app_layout import AppLayout


class DummyCore:
    def get_slots_state(self):
        return [
            {
                "slot_id": f"SLOT-{i+1}",
                "symbol": "BTC/USDC",
                "status": "IDLE",
                "mode": "STANDBY",
                "health": "OK",
                "last_event": None,
                "updated_at": "now"
            }
            for i in range(12)
        ]

    def get_global_risk(self):
        return {
            "status": "UNKNOWN",
            "reason": None,
            "last_event": None,
            "updated_at": "now"
        }


if __name__ == "__main__":
    app = AppLayout(DummyCore())
    app.mainloop()
