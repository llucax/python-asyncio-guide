import time
import asyncio

t0: float

async def flush() -> None:
    global t0
    print(f"flush: starting at {time.time() - t0:.1f}s")
    await asyncio.sleep(3)
    print(f"flush: finished at {time.time() - t0:.1f}s")

async def do_work() -> None:
    global t0
    try:
        print(f"work: starting at {time.time() - t0:.1f}s")
        await asyncio.sleep(2)
        print(f"work: finished at {time.time() - t0:.1f}s")
    finally:
        await flush()

async def do_work_with_timeout() -> None:
    async with asyncio.timeout(1):
        await do_work()

async def main() -> None:
    global t0
    t0 = time.time()
    try:
        async with asyncio.timeout(1.5):
            async with asyncio.TaskGroup() as tg:
                tg.create_task(do_work_with_timeout(), name="do-work")

                print(f"main: waiting for 5s at {time.time() - t0:.1f}s")
                await asyncio.sleep(5)
    except asyncio.TimeoutError:
        print(f"main: timeout at {time.time() - t0:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
