import asyncio
import time

T0 = time.monotonic()


def stamp() -> str:
    return f"{time.monotonic() - T0:.1f}s"


async def flush_file_buffers(path: str) -> None:
    print(f"flush: starting {path} at {stamp()}")
    await asyncio.sleep(2)
    print(f"flush: finished {path} at {stamp()}")


async def write_output_file(path: str) -> None:
    print(f"writer: starting {path} at {stamp()}")
    try:
        await asyncio.sleep(2)
        print(f"writer: finished {path} at {stamp()}")
    finally:
        await flush_file_buffers(path)


async def run_write_with_timeout(path: str) -> None:
    async with asyncio.timeout(1):
        await write_output_file(path)


async def run_batch_job(path: str) -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(run_write_with_timeout(path), name="write-output")
        print(f"batch: waiting for 5s at {stamp()}")
        await asyncio.sleep(5)


async def main() -> None:
    try:
        async with asyncio.timeout(1.5):
            await run_batch_job("report.txt")
    except TimeoutError:
        print(f"main: shutdown timeout at {stamp()}")


if __name__ == "__main__":
    asyncio.run(main())
