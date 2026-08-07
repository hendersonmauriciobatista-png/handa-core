class ArmedValidator:

    def __init__(self, max_cycles: int = 3):
        self.max_cycles = max_cycles
        self.current_cycles = 0

    def reset(self):
        self.current_cycles = 0

    def register_cycle(self):
        self.current_cycles += 1

    def is_valid(self) -> bool:
        return self.current_cycles <= self.max_cycles
