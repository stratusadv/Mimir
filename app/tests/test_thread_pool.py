from __future__ import annotations

import pytest

from concurrent.futures import ThreadPoolExecutor

from thread_pool import ThreadPool


def test_pool_shuts_down_after_a_clean_exit() -> None:
    pool = ThreadPool(2)

    with pool as thread_executor:
        assert thread_executor.submit(lambda: 21 * 2).result() == 42

    with pytest.raises(RuntimeError):
        _ = pool.executor.submit(lambda: 1)


def test_pool_shuts_down_after_an_exception() -> None:
    pool = ThreadPool(2)

    with pytest.raises(RuntimeError):
        with pool as thread_executor:
            _ = thread_executor.submit(lambda: 1)
            message = 'work abandoned'

            raise RuntimeError(message)

    with pytest.raises(RuntimeError):
        _ = pool.executor.submit(lambda: 1)


def test_pool_yields_a_thread_pool_executor() -> None:
    with ThreadPool(3) as thread_executor:
        assert isinstance(thread_executor, ThreadPoolExecutor)
        assert thread_executor._max_workers == 3
