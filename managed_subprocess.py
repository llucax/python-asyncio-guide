import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

async def terminate_subprocess(
    proc: asyncio.subprocess.Process,
    *,
    kill_after: float = 1.0,
) -> None:
    if proc.returncode is not None:
        return

    try:
        proc.terminate()
    except ProcessLookupError:
        await proc.wait()
        return

    try:
        async with asyncio.timeout(kill_after):
            await proc.wait()
    except TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            await proc.wait()
            return
        await proc.wait()

@asynccontextmanager
async def managed_subprocess(
    program: str,
    *args: str,
    **kwargs: Any,
) -> AsyncIterator[asyncio.subprocess.Process]:
    proc = await asyncio.create_subprocess_exec(program, *args, **kwargs)
    try:
        yield proc
    finally:
        await terminate_subprocess(proc)
