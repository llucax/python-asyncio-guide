import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

async def send_report(name: str, elapsed: float, *, failed: bool=False) -> None:
    await asyncio.sleep(0.1)
    result = "failed" if failed else "succeeded"
    print(f"Sent report: {name!r} {result} in {elapsed:.2f} seconds")

@asynccontextmanager
async def reporing_time(name: str) -> AsyncIterator[None]: # (1)!
    start = time.monotonic()
    try:
        yield
    except BaseException:
        elapsed = time.monotonic() - start
        await send_report(name, elapsed, failed=True)
        raise
    else:
        elapsed = time.monotonic() - start
        await send_report(name, elapsed)
async def refresh_cache() -> None:
        await asyncio.sleep(0.25)
        print("cache data is ready")

async def main() -> None:
    print("Refreshing cache 1...")
    async with reporing_time("refresh cache 1"):
        await refresh_cache()

    print("Refreshing cache 2...")
    try:
        async with asyncio.timeout(0.2):
            async with reporing_time("refresh cache 2"):
                await refresh_cache()
    except asyncio.TimeoutError:
        print("refresh_cache() took too long and was cancelled")

if __name__ == "__main__":
    asyncio.run(main())
