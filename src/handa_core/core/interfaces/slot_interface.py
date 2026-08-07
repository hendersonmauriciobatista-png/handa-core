from abc import ABC, abstractmethod


class SlotInterface(ABC):

    @abstractmethod
    def assign_asset(self, asset: str):
        pass

    @abstractmethod
    def get_state(self):
        pass

    @abstractmethod
    def get_current_asset(self) -> str:
        pass
