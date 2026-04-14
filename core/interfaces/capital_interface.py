from abc import ABC, abstractmethod


class CapitalInterface(ABC):

    @abstractmethod
    def calculate_allocation(self, eligible_slots: int) -> float:
        pass

    @abstractmethod
    def validate_allocation(self, asset: str, amount: float) -> bool:
        pass
