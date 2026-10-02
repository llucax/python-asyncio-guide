import asyncio
import time

async def blocking_task(t0: float) -> str:
    elapsed: float = time.monotonic() - t0
    print(f"blocking_task: starting synchronous sleep at {elapsed:.1f}s...")
    time.sleep(2) # (1)!
    elapsed = time.monotonic() - t0
    print(f"blocking_task: done sleeping at {elapsed:.1f}s")
    return "blocking result"

async def polite_task(t0: float) -> str:
    for i in range(4):
        elapsed: float = time.monotonic() - t0
        print(f"polite_task: tick {i} at {elapsed:.1f}s")
        await asyncio.sleep(0.5)
        elapsed = time.monotonic() - t0
        print(f"polite_task: finished tick {i} at {elapsed:.1f}s")
    return "polite result"

async def main() -> None:
    t0: float = time.monotonic()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(blocking_task(t0), name="blocking-task")
        tg.create_task(polite_task(t0), name="polite-task")
    elapsed: float = time.monotonic() - t0
    print(f"Total time: {elapsed:.1f}s")

if __name__ == "__main__":
    asyncio.run(main(), debug=True)
