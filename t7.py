from __future__ import annotations
import asyncio
import time
from contextlib import AbstractAsyncContextManager
from typing import Self, override # (1)!

class Timer(AbstractAsyncContextManager["Timer"]): # (2)!
    """Async context manager that measures wall-clock time of an async block."""

    def __init__(self, label: str) -> None:
        self.label: str = label
        self.elapsed: float = 0.0
        self._start: float = 0.0

    @override
    async def __aenter__(self) -> Self:
        self._start = time.monotonic()
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None | bool:
        self.elapsed = time.monotonic() - self._start
        print(f"[{self.label}] {self.elapsed:.3f}s")

async def main() -> None:
    async with Timer("sleep test") as t:
        await asyncio.sleep(0.25)
    print(f"Elapsed was {t.elapsed:.3f}s")

if __name__ == "__main__":
    asyncio.run(main())
