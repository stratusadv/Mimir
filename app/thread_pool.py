from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import TracebackType


class ThreadPool:
    def __init__(self, workers_max: int) -> None:
        self.executor = ThreadPoolExecutor(max_workers=workers_max)

    def __enter__(self) -> ThreadPoolExecutor:
        return self.executor

    def __exit__(
            self,
            exception_type: type[BaseException] | None,
            exception_value: BaseException | None,
            traceback: TracebackType | None,
    ) -> None:
        wait = exception_type is None
        self.executor.shutdown(wait=wait, cancel_futures=not wait)
