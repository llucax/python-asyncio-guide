---
title: Blocking Code
description: >-
  Safely integrate synchronous and blocking code into async programs using
  asyncio.to_thread() and loop.run_in_executor(). Understand why blocking
  calls freeze the event loop and how to fix them.
---

# Blocking Code

Not everything in the Python ecosystem is async. You will need to call
libraries that talk to databases, read files, or crunch numbers -- and many of
them are synchronous. That is fine. Asyncio has good tools for bridging the
gap. The catch is that you have to use them *deliberately*, because calling a
blocking function directly inside a coroutine is one of the easiest ways to
break an async program.

## The Problem: Blocking the Event Loop

The event loop runs in a single thread. When you `await` something, control
returns to the loop so it can service other tasks. But if you call a function
that blocks -- `time.sleep()`, a synchronous HTTP request, a heavy computation
-- the loop cannot switch away. Every other task, every pending callback, every
open connection just *waits*.

Here is a concrete example. Two tasks run concurrently: one does a blocking
sleep, the other tries to make progress alongside it:

```python title="blocking_freeze.py"
import asyncio
import time

async def blocking_task() -> str:
    print("blocking_task: starting synchronous sleep...")
    time.sleep(2)  # BUG: blocks the event loop for 2 seconds
    print("blocking_task: done sleeping")
    return "blocking result"

async def polite_task() -> str:
    for i in range(4):
        print(f"polite_task: tick {i}")
        await asyncio.sleep(0.5)
    return "polite result"

async def main() -> None:
    t0: float = time.monotonic()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(blocking_task())
        tg.create_task(polite_task())
    elapsed: float = time.monotonic() - t0
    print(f"Total time: {elapsed:.1f}s")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python blocking_freeze.py"
blocking_task: starting synchronous sleep...
blocking_task: done sleeping
polite_task: tick 0
polite_task: tick 1
polite_task: tick 2
polite_task: tick 3
Total time: 4.0s
```

`polite_task` did not start printing until the blocking sleep finished. The two
tasks ran *sequentially*, not concurrently, even though they were in the same
`TaskGroup`. Worse, total wall time was 4 seconds instead of the 2 seconds you
would expect from concurrent execution. In a real application, those 2 frozen
seconds mean dropped connections, missed heartbeats, and unresponsive
services.

!!! warning

    Asyncio debug mode (covered in [Debugging](../everyday-asyncio/debugging.md))
    logs a warning when a callback blocks the loop for more than 100 ms, but it
    cannot *prevent* the freeze. The only fix is to not block the loop in the
    first place.

## `asyncio.to_thread()`

[`asyncio.to_thread()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread)
is the standard way to call a blocking function without freezing the event
loop. It runs the function in a separate thread and returns an awaitable that
completes when the function finishes. The event loop stays responsive in the
meantime.

The signature is simple:

```python
result = await asyncio.to_thread(sync_function, arg1, arg2, ...)
```

You pass the callable and its arguments -- *not* a call expression. `to_thread`
handles running it in a thread and shuttling the result back.

Here is the fixed version of the freezing example:

```python title="blocking_fixed.py"
import asyncio
import time

def blocking_work() -> str:
    """A plain synchronous function -- no async keyword."""
    print("blocking_work: starting synchronous sleep...")
    time.sleep(2)
    print("blocking_work: done sleeping")
    return "blocking result"

async def polite_task() -> str:
    for i in range(4):
        print(f"polite_task: tick {i}")
        await asyncio.sleep(0.5)
    return "polite result"

async def main() -> None:
    t0: float = time.monotonic()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(asyncio.to_thread(blocking_work))
        tg.create_task(polite_task())
    elapsed: float = time.monotonic() - t0
    print(f"Total time: {elapsed:.1f}s")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python blocking_fixed.py"
blocking_work: starting synchronous sleep...
polite_task: tick 0
polite_task: tick 1
polite_task: tick 2
polite_task: tick 3
blocking_work: done sleeping
Total time: 2.0s
```

Now both tasks run concurrently. `polite_task` prints its ticks while
`blocking_work` sleeps in a background thread. Total time is 2 seconds --
the duration of the slowest task, as you would expect.

Notice that `blocking_work` is a plain `def` function, not `async def`. That
is the whole point: you already have synchronous code and you need to call it
from an async context. `to_thread` bridges the gap.

!!! tip "Trio users"

    `asyncio.to_thread()` is equivalent to
    `trio.to_thread.run_sync()`. Same idea, same purpose.

!!! note

    `to_thread` uses Python's default
    [`ThreadPoolExecutor`](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor).
    The default pool size was changed to `min(32, os.cpu_count() + 4)` in Python
    3.8. For most I/O-bound workloads this is plenty. If you need a larger pool,
    pass a custom executor to `loop.run_in_executor()` instead.

## Thread Safety

Once you push work into a thread, you are in multi-threaded territory, and all
the usual rules apply: shared mutable state needs synchronization.

There are two directions to worry about:

**1. The threaded function accessing shared data.** If your blocking function
reads or writes variables that other tasks also touch, you need a
[`threading.Lock`](https://docs.python.org/3/library/threading.html#threading.Lock)
-- *not* an `asyncio.Lock`, which is not thread-safe. In practice, the
simplest approach is to design your blocking functions to be self-contained:
pass everything in as arguments, return the result, don't mutate external
state.

**2. The threaded function calling back into asyncio.** Asyncio objects --
tasks, futures, queues, locks -- are *not* thread-safe. You cannot call
`asyncio.Queue.put()` from a thread. If the threaded function needs to send
data back to the event loop while it is still running, use
[`loop.call_soon_threadsafe()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon_threadsafe):

```python title="threadsafe_callback.py"
import asyncio
import time

results: list[str] = []

def slow_producer(loop: asyncio.AbstractEventLoop) -> None:
    """Runs in a worker thread. Pushes results to the event loop."""
    for i in range(3):
        time.sleep(0.5)
        value: str = f"item-{i}"
        loop.call_soon_threadsafe(results.append, value)

async def main() -> None:
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    await asyncio.to_thread(slow_producer, loop)
    print(f"Results: {results}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python threadsafe_callback.py"
Results: ['item-0', 'item-1', 'item-2']
```

!!! note

    `asyncio.get_running_loop()` and `loop.call_soon_threadsafe()` are low-level
    event loop APIs covered in detail in
    [Chapter 4](../the-low-level-toolkit/loop-access-and-inspection.md).
    They appear here because they are the *only* way to safely communicate from
    a background thread back to the event loop -- there is no high-level
    alternative for this pattern.

`call_soon_threadsafe` schedules a callback on the event loop from any thread.
It is the *only* safe way to touch event loop internals from outside the loop
thread. For more complex patterns -- like feeding items into an
`asyncio.Queue` from a thread -- wrap the `queue.put_nowait()` call inside
`call_soon_threadsafe`.

!!! warning

    Do not pass asyncio primitives (locks, events, queues) directly to a thread
    and call their methods there. It will appear to work in simple cases and
    break under load. Always go through `call_soon_threadsafe` or use
    `threading`-based synchronization primitives instead.

## `ProcessPoolExecutor` for CPU-Bound Work

`to_thread` solves the problem for I/O-bound blocking work -- file reads,
network calls, database queries. But for CPU-bound work -- number crunching,
image processing, compression -- threads do not help. Python's Global
Interpreter Lock (GIL) means only one thread executes Python bytecode at a
time. A CPU-heavy function in a thread still starves the event loop because
both the thread and the loop are competing for the same GIL.

The solution is to use a separate *process*. A
[`ProcessPoolExecutor`](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ProcessPoolExecutor)
runs work in a pool of child processes, each with its own GIL. You call it
through
[`loop.run_in_executor()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor):

```python title="cpu_bound.py"
import asyncio
import math
import time
from concurrent.futures import ProcessPoolExecutor

def is_prime(n: int) -> bool:
    """A deliberately slow primality check."""
    if n < 2:
        return False
    for i in range(2, int(math.isqrt(n)) + 1):
        if n % i == 0:
            return False
    return True

async def check_primes(numbers: list[int]) -> dict[int, bool]:
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as pool:
        async with asyncio.TaskGroup() as tg:
            tasks: list[tuple[int, asyncio.Task[bool]]] = [
                (n, tg.create_task(loop.run_in_executor(pool, is_prime, n)))
                for n in numbers
            ]
    return {n: t.result() for n, t in tasks}

async def main() -> None:
    numbers: list[int] = [
        104_729, 104_743, 999_999_937, 1_000_000_007, 1_000_000_009,
    ]
    t0: float = time.monotonic()
    results: dict[int, bool] = await check_primes(numbers)
    elapsed: float = time.monotonic() - t0
    for n, prime in results.items():
        print(f"{n:>13,} -> {'prime' if prime else 'composite'}")
    print(f"Checked {len(numbers)} numbers in {elapsed:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python cpu_bound.py"
      104,729 -> prime
      104,743 -> prime
  999,999,937 -> prime
1,000,000,007 -> prime
1,000,000,009 -> prime
Checked 5 numbers in 0.43s
```

!!! note

    Like the `call_soon_threadsafe` example above, this recipe uses the low-level
    APIs `asyncio.get_running_loop()` and `loop.run_in_executor()`, which are
    covered in [Chapter 4](../the-low-level-toolkit/loop-access-and-inspection.md).
    `run_in_executor` is the only built-in way to dispatch work to a
    `ProcessPoolExecutor` from async code, so you will see it whenever CPU-bound
    offloading comes up.

A few things to note:

- `run_in_executor` requires the running loop, which you get with
  `asyncio.get_running_loop()`.
- The executor is a `ProcessPoolExecutor`, not the default `ThreadPoolExecutor`.
  That is the key difference from `to_thread`.
- Each function call and its arguments must be
  [picklable](https://docs.python.org/3/library/pickle.html), because they are
  serialized and sent to a child process. Lambda functions, closures, and
  objects with unpicklable state will raise a `PicklingError`.
- The `with ProcessPoolExecutor()` block shuts down the pool cleanly when the
  work is done. In a long-running service, you would typically create the pool
  once at startup and reuse it.

!!! info

    Only reach for `ProcessPoolExecutor` when the work is genuinely CPU-bound.
    Process creation and inter-process communication have significant overhead
    compared to threads. For I/O-bound blocking calls, `to_thread` is simpler
    and faster.

## When to Use What

Here is the short decision guide:

| Situation | Tool | Why |
| :--- | :--- | :--- |
| **Async library** (aiohttp, asyncpg, etc.) | Just `await` it | Already non-blocking |
| **Blocking I/O** (file reads, sync HTTP, DB drivers) | `asyncio.to_thread()` | Offloads to a thread; loop stays free |
| **CPU-bound work** (math, compression, image processing) | `loop.run_in_executor()` + `ProcessPoolExecutor` | Bypasses the GIL with a separate process |

Two rules of thumb:

1. **Default to `to_thread()`.** Most blocking code you encounter is I/O-bound.
   Thread overhead is low, there is no pickling requirement, and the API is a
   single function call.
2. **Reach for processes only when threads are not enough.** If you profile and
   find a CPU-bound function that still blocks the loop even with `to_thread`,
   that is when you switch to `ProcessPoolExecutor`.

If you find yourself wrapping *every* call in `to_thread`, that is a signal
that you might be better off with a natively async library instead. Wrapping
synchronous `requests` in `to_thread` works, but switching to
[aiohttp](https://docs.aiohttp.org/) or
[httpx](https://www.python-httpx.org/) (with its async API) will give you
better performance and cleaner code.

---
