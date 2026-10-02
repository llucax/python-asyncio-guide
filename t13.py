import asyncio
import sys
from managed_subprocess import managed_subprocess # (1)!

async def main() -> None:
    try:
        async with managed_subprocess(
            sys.executable,
            "-c",
            "import time; time.sleep(10)",
        ) as proc:
            async with asyncio.timeout(0.5):
                await proc.wait()
    except TimeoutError:
        print("deadline expired; terminating child")

    print("child finished")

if __name__ == "__main__":
    asyncio.run(main())

