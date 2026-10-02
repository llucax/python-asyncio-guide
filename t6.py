import asyncio
import time

T0 = time.monotonic()


def stamp() -> str:
    return f"{time.monotonic() - T0:.1f}s"


async def flush_file_buffers(path: str) -> None:
    print(f"flush: starting {path} at {stamp()}")
    await asyncio.sleep(2)
    print(f"flush: finished {path} at {stamp()}")


async def write_output_file(
    path: str,
    cleanup_tg: asyncio.TaskGroup,
) -> None:
    print(f"writer: starting {path} at {stamp()}")
    try:
        await asyncio.sleep(2)
        print(f"writer: finished {path} at {stamp()}")
    finally:
        flush_task: asyncio.Task[None] = cleanup_tg.create_task(
            flush_file_buffers(path),
            name="flush-report",
        )
        try:
            await asyncio.shield(flush_task)
        except asyncio.CancelledError:
            print(
                f"writer: shield cancelled, flush continues "
                f"under owner at {stamp()}"
            )
            raise


async def run_write_with_timeout(
    path: str,
    cleanup_tg: asyncio.TaskGroup,
) -> None:
    async with asyncio.timeout(1):
        await write_output_file(path, cleanup_tg)


async def run_batch_job(
    path: str,
    cleanup_tg: asyncio.TaskGroup,
) -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(
            run_write_with_timeout(path, cleanup_tg),
            name="write-output",
        )
        print(f"batch: waiting for 5s at {stamp()}")
        await asyncio.sleep(5)


async def main() -> None:
    async with asyncio.TaskGroup() as cleanup_tg:
        try:
            async with asyncio.timeout(1.5):
                await run_batch_job("report.txt", cleanup_tg)
        except TimeoutError:
            print(f"main: shutdown timeout at {stamp()}")
    print(f"main: all cleanup done at {stamp()}")


if __name__ == "__main__":
    asyncio.run(main())
