from enum import Enum


class FeedScenario(Enum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    SIDEWAYS = "sideways"


class MockFeed:
    """
    Feed de mercado simulado com cenários determinísticos.
    Cada chamada avança um 'tick'.
    """

    def __init__(self, scenario=FeedScenario.UPTREND, start_price=100):
        self.scenario = scenario
        self.price = start_price
        self.tick = 0

    def get_market_data(self):
        self.tick += 1

        if self.scenario == FeedScenario.UPTREND:
            self.price += 1

        elif self.scenario == FeedScenario.DOWNTREND:
            self.price -= 1

        elif self.scenario == FeedScenario.SIDEWAYS:
            # Oscila levemente
            self.price += (-1) ** self.tick

        return {
            "price": self.price,
            "volume": 1,
            "tick": self.tick,
            "scenario": self.scenario.value
        }
