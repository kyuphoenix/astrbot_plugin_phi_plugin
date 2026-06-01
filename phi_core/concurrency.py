from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class AsyncKeyedLock:
    """Serialize async work by key and drop idle locks after use."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._ref_counts: dict[str, int] = {}

    async def run(self, key: str, action: Callable[[], Awaitable[T]]) -> T:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        self._ref_counts[key] = self._ref_counts.get(key, 0) + 1
        try:
            async with lock:
                return await action()
        finally:
            remaining = self._ref_counts.get(key, 1) - 1
            if remaining <= 0:
                self._ref_counts.pop(key, None)
                self._locks.pop(key, None)
            else:
                self._ref_counts[key] = remaining

    def active_count(self) -> int:
        return len(self._locks)
