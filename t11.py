import asyncio
import sys

async def main() -> None:
    timed_out = False
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import time; time.sleep(10)",
    )

    try:
        async with asyncio.timeout(0.5):
            await proc.wait()
    except TimeoutError:
        timed_out = True
    finally:
        if proc.returncode is None:
            if timed_out:
                print("deadline expired; terminating child")
            else:
                print("cleanup: terminating unfinished child")
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            try:
                async with asyncio.timeout(1):
                    await proc.wait()
            except TimeoutError:
                print("child ignored SIGTERM; killing it")
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()

    print(f"child finished with return code: {proc.returncode}")

if __name__ == "__main__":
    asyncio.run(main())

