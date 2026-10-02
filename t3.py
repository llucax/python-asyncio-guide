import asyncio
import math
import time
from concurrent.futures import ProcessPoolExecutor

def is_prime(t0: float, n: int) -> bool: # (1)!
    """A deliberately slow primality check."""
    print(f"Checking {n:,}...")
    prime = True
    if n < 2:
        prime = False
    for i in range(2, int(math.isqrt(n)) + 1):
        if n % i == 0:
            prime = False
    elapsed: float = time.monotonic() - t0
    print(f"Done checking {n:,} after {elapsed:.2f}s")
    return prime

async def main() -> None:
    numbers: list[int] = [
        104_729, 104_743, 999_999_937, 500_000_000_000_001, 500_000_000_000_007,
    ]
    t0: float = time.monotonic()
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as pool:
        async with asyncio.TaskGroup() as tg:
            async def is_prime_coro(n: int) -> bool: # (2)!
                return await loop.run_in_executor(pool, is_prime, t0, n)
            tasks: dict[int, asyncio.Task[bool]] = {
                n: tg.create_task(is_prime_coro(n), name=f"prime-check-{n}")
                for n in numbers
            }

        results: dict[int, bool] =  {n: t.result() for n, t in tasks.items()}

    elapsed: float = time.monotonic() - t0
    for n, prime in results.items():
        print(f"{n:>20,} -> {'prime' if prime else 'composite'}")
    print(f"Checked {len(numbers)} numbers in {elapsed:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
