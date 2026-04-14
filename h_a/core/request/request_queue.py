from collections import deque
from typing import Deque, List

from h_a.core.request.request_model import Request


class RequestQueue:
    def __init__(self, max_size: int = 50):
        self._queue: Deque[Request] = deque(maxlen=max_size)

    def add(self, request: Request) -> None:
        self._queue.append(request)

    def list_all(self) -> List[Request]:
        return list(self._queue)

    def clear(self) -> None:
        self._queue.clear()
