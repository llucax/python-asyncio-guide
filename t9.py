import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from types import TracebackType
from typing import override

class ConnectionPool(AbstractAsyncContextManager["ConnectionPool"]):
    """Simulates a pool of async connections."""

    def __init__(self, dsn: str, size: int) -> None:
        self.dsn = dsn
        self.size = size
        self._connections: list[str] = []
        self._pending: int = 0

    async def open(self) -> None:
        for i in range(self.size):
            await asyncio.sleep(0.02)
            self._connections.append(f"conn-{i}")
        print(f"Pool opened: {self.size} connections to {self.dsn}")

    async def execute(self, query: str) -> str:
        self._pending += 1
        await asyncio.sleep(0.05)
        self._pending -= 1
        return f"OK: {query}"

    async def aclose(self) -> None:
        while self._pending > 0:
            await asyncio.sleep(0.01)
            self._pending -= 1
        self._connections.clear()
        print("Pool released: all connections returned")

    @override
    async def __aenter__(self) -> "ConnectionPool":
        await self.open()
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

@asynccontextmanager
async def app_context() -> AsyncIterator[ConnectionPool]:
    """Higher-level context that wires up the pool with app-specific config."""
    async with ConnectionPool("postgres://localhost/prod", size=3) as pool:
        print("App ready")
        try:
            yield pool
        finally:
            print("App shutting down")

async def main() -> None:
    async with app_context() as pool:
        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(pool.execute("SELECT 1"), name="select-1")
            t2 = tg.create_task(pool.execute("SELECT 2"), name="select-2")
        for result in (t1.result(), t2.result()):
            print(f"  {result}")

if __name__ == "__main__":
    asyncio.run(main())
