from abc import ABC, abstractmethod
from typing import List


class MarketInterface(ABC):

    @abstractmethod
    def get_ranking(self) -> List[str]:
        """Return ordered list of ranked assets."""
        pass

    @abstractmethod
    def recalculate_ranking(self) -> None:
        """Trigger ranking recalculation based on structural event."""
        pass
