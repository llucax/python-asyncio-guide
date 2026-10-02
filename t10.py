import asyncio
import sys

async def main() -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        (
            "import time\n"
            "for i in range(3):\n"
            "    print(i, flush=True)\n"
            "    time.sleep(0.2)\n"
        ),
        stdout=asyncio.subprocess.PIPE,
    )

    assert proc.stdout is not None
    while line := await proc.stdout.readline():
        print(f"child: {line.decode().strip()}")

    await proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
