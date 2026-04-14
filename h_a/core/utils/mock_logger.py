class MockLogger:
    def info(self, payload):
        print("LOG:", payload)
