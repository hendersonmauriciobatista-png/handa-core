from abc import ABC, abstractmethod


class RiskInterface(ABC):

    @abstractmethod
    def get_current_regime(self) -> str:
        """Return current global market regime."""
        pass

    @abstractmethod
    def get_igr(self) -> float:
        """Return current Global Risk Index (IGR)."""
        pass

    @abstractmethod
    def is_system_stressed(self) -> bool:
        """Return True if system is in stressed state."""
        pass
