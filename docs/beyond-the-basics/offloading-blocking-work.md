---
title: Offloading Blocking Work
description: >-
  Offload synchronous and blocking work from async programs with
  asyncio.to_thread() and loop.run_in_executor(). Learn when to use threads,
  when to use processes, and how to keep the event loop responsive.
---

# Offloading Blocking Work

[The Basics](../the-basics/index.md) already covered the core rule: do not
block the event loop. This section picks up at the next question: what do you
do when you still need to call synchronous code?

Not everything in the Python ecosystem is async. You will need to call
libraries that talk to databases, read files, or crunch numbers -- and many of
them are synchronous. That is fine. Asyncio has good tools for offloading that
work without freezing the loop. The catch is that you have to use them
*deliberately*, because calling a blocking function directly inside a coroutine
is one of the easiest ways to break an async program.

!!! Info

    This section focuses on the decision-making: what blocks the loop, when to
    use `#!py to_thread()`, and when to escalate to a process pool. Use the
    official [Coroutines and Tasks][official-tasks], [Event
    Loop][official-event-loop], and [Developing with asyncio][official-dev]
    pages for full executor and threading details.

## The Problem

The event loop runs in a single thread. When you [`await`][await] something,
control returns to the loop so it can service other tasks. But if you call a
function that blocks -- `#!py time.sleep()`, a synchronous HTTP request, a
heavy computation -- the loop cannot switch away. Every other task, every
pending callback, every open connection just *waits*.

Here is a concrete example. Two tasks run concurrently: one does a blocking
sleep, the other tries to make progress alongside it:

```python title="blocking_freeze.py" hl_lines="7"
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
    asyncio.run(main())
```

1. **BUG:** blocks the event loop for 2 seconds.

```text title="$ python blocking_freeze.py"
blocking_task: starting synchronous sleep at 0.0s...
blocking_task: done sleeping at 2.0s
polite_task: tick 0 at 2.0s
polite_task: finished tick 0 at 2.5s
polite_task: tick 1 at 2.5s
polite_task: finished tick 1 at 3.0s
polite_task: tick 2 at 3.0s
polite_task: finished tick 2 at 3.5s
polite_task: tick 3 at 3.5s
polite_task: finished tick 3 at 4.0s
Total time: 4.0s
```

`#!py polite_task` did not start printing until the blocking sleep finished.
The two tasks ran *sequentially*, not concurrently, even though they were in
the same [`TaskGroup`][taskgroup]. Worse, total wall time was 4 seconds instead
of the 2 seconds you would expect from concurrent execution. In a real
application, those 2 frozen seconds mean dropped connections, missed
heartbeats, and unresponsive services.

!!! Danger

    As you will see, there are solutions and escape hatches, but complexity
    can explode very quickly once you need to offload blocking work. Do not let
    this happen in the first place. If you have a choice, use async libraries
    that fit your needs; avoid the temptation of implementing it yourself. They
    will be more efficient and easier to work with than the custom solutions
    presented here.

## `#!py asyncio.to_thread()`

[`asyncio.to_thread()`][asyncio-to-thread] is the standard way to call a
blocking function without freezing the event loop. It runs the function in a
separate thread and returns an awaitable that completes when the function
finishes. The event loop stays responsive in the meantime.

The signature is simple:

```python
result = await asyncio.to_thread(sync_function, arg1, arg2, ...)
```

You pass the callable and its arguments -- *not* a call expression.
[`asyncio.to_thread()`][asyncio-to-thread] handles running it in a thread and
shuttling the result back.

Here is the fixed version of the freezing example:

```python title="blocking_fixed.py" hl_lines="4 26"
import asyncio
import time

def blocking_work(t0: float) -> str: # (1)!
    """A plain synchronous function -- no async keyword."""
    elapsed: float = time.monotonic() - t0
    print(f"blocking_work: starting synchronous sleep at {elapsed:.1f}s...")
    time.sleep(2)
    elapsed = time.monotonic() - t0
    print(f"blocking_work: done sleeping at {elapsed:.1f}s")
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
        tg.create_task(
            asyncio.to_thread(blocking_work, t0), # (2)!
            name="blocking-work",
        )
        tg.create_task(polite_task(t0), name="polite-task")
    elapsed: float = time.monotonic() - t0
    print(f"Total time: {elapsed:.1f}s")

if __name__ == "__main__":
    asyncio.run(main())
```

1. `blocking_work` is now a plain synchronous function, not a coroutine.
2. `asyncio.to_thread()` runs `blocking_work` in background thread now.

```text title="$ python blocking_fixed.py"
blocking_work: starting synchronous sleep at 0.0s...
polite_task: tick 0 at 0.0s
polite_task: finished tick 0 at 0.5s
polite_task: tick 1 at 0.5s
polite_task: finished tick 1 at 1.0s
polite_task: tick 2 at 1.0s
polite_task: finished tick 2 at 1.5s
polite_task: tick 3 at 1.5s
blocking_work: done sleeping at 2.0s
polite_task: finished tick 3 at 2.0s
Total time: 2.0s
```

Now both tasks run concurrently. `#!py polite_task` prints its ticks while
`#!py blocking_work` sleeps in a background thread. Total time is 2 seconds --
the duration of the slowest task, as you would expect.

Notice that `#!py blocking_work` is a plain `#!py def` function, not `#!py
async def`. That is the whole point: you already have synchronous code and you
need to call it from an async context.
[`asyncio.to_thread()`][asyncio-to-thread] bridges the gap.

!!! Tip "Trio"

    [`asyncio.to_thread()`][asyncio-to-thread] is equivalent to
    [`trio.to_thread.run_sync()`][trio-to-thread-run-sync]. Same idea, same
    purpose.

!!! Note

    [`asyncio.to_thread()`][asyncio-to-thread] uses Python's default
    [`ThreadPoolExecutor`][threadpoolexecutor]. The default pool size at the
    time of writing is `#!py min(32, os.cpu_count() + 4)`. For most I/O-bound
    workloads this is plenty. If you need a larger pool, pass a custom executor
    to [`loop.run_in_executor()`][loop-run-in-executor] instead.

### Thread Safety

Once you push work into a thread, you are in multi-threaded territory, and
all the usual rules apply: shared mutable state needs synchronization.

There are two directions to worry about:

1. **The threaded function accessing shared data.** If your blocking function
   reads or writes variables that other tasks also touch, you need a
   [`threading.Lock`][threading-lock] -- *not* an
   [`asyncio.Lock`][asyncio-lock], which is not thread-safe. In practice, the
   simplest approach is to design your blocking functions to be self-contained:
   pass everything in as arguments, return the result, don't mutate external
   state.

2. **The threaded function calling back into asyncio.** Asyncio objects --
   tasks, futures, queues, locks -- are *not* thread-safe. You cannot call
   `#!py asyncio.Queue.put()` from a thread. If the threaded function needs to
   send data back to the event loop while it is still running, use
   [`loop.call_soon_threadsafe()`][loop-call-soon-threadsafe]:

```python title="threadsafe_callback.py" hl_lines="11"
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

!!! Note

    [`asyncio.get_running_loop()`][asyncio-get-running-loop] and
    [`loop.call_soon_threadsafe()`][loop-call-soon-threadsafe] are low-level
    event loop APIs covered in detail in [Loop Access and
    Inspection](../the-low-level-toolkit/loop-access-and-inspection.md) in [The
    Low-Level Toolkit](../the-low-level-toolkit/index.md). They appear here
    because they are the *only* way to safely communicate from a background
    thread back to the event loop -- there is no high-level alternative for
    this pattern.

[`loop.call_soon_threadsafe()`][loop-call-soon-threadsafe] schedules a callback
on the event loop from any thread. It is the *only* safe way to touch event
loop internals from outside the loop thread. For more complex patterns -- like
feeding items into an [`asyncio.Queue`][asyncio-queue] from a thread -- wrap
the `#!py queue.put_nowait()` call inside
[`loop.call_soon_threadsafe()`][loop-call-soon-threadsafe].

!!! Warning

    Do not pass asyncio primitives (locks, events, queues) directly to a thread
    and call their methods there. It will appear to work in simple cases and
    break under load. Always go through
    [`loop.call_soon_threadsafe()`][loop-call-soon-threadsafe] or use
    [`threading`][threading]-based synchronization primitives instead.

## `#!py ProcessPoolExecutor` for CPU-Bound Work

[`asyncio.to_thread()`][asyncio-to-thread] solves the problem for I/O-bound
blocking work -- file reads, network calls, database queries. But for
CPU-bound work -- number crunching, image processing, compression -- threads do
not help. Python's Global
Interpreter Lock (GIL) means only one thread executes Python bytecode at a
time. A CPU-heavy function in a thread still starves the event loop because
both the thread and the loop are competing for the same GIL.

The solution is to use a separate *process*. A
[`ProcessPoolExecutor`][processpoolexecutor]
runs work in a pool of child processes, each with its own GIL. You call it
through
[`loop.run_in_executor()`][loop-run-in-executor]:

```python title="cpu_bound.py" hl_lines="6 25 27-28 30"
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
    with ProcessPoolExecutor() as pool: # (2)!
        async with asyncio.TaskGroup() as tg:
            async def is_prime_coro(n: int) -> bool: # (3)!
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
```

1. A CPU-bound sync function.
2. Create a `ProcessPoolExecutor` to run work in child processes.
3. We need to wrap the `#!py loop.run_in_executor()` call into a coroutine
   because it returns a [`Future`][asyncio-future], not a coroutine, and `#!py
   tg.create_task()` requires a coroutine. We'll get into what a `Future` is in
   [The Low-Level Toolkit -- Futures](../the-low-level-toolkit/futures.md).

```text title="$ python cpu_bound.py"
Checking 104,729...
Done checking 104,729 after 0.11s
Checking 104,743...
Done checking 104,743 after 0.11s
Checking 999,999,937...
Done checking 999,999,937 after 0.11s
Checking 500,000,000,000,001...
Checking 500,000,000,000,007...
Done checking 500,000,000,000,001 after 1.29s
Done checking 500,000,000,000,007 after 1.30s
             104,729 -> prime
             104,743 -> prime
         999,999,937 -> prime
 500,000,000,000,001 -> composite
 500,000,000,000,007 -> composite
Checked 5 numbers in 1.31s
```

!!! Note

    Like the `#!py call_soon_threadsafe` example above, this recipe uses the
    low-level APIs [`asyncio.get_running_loop()`][asyncio-get-running-loop] and
    [`loop.run_in_executor()`][loop-run-in-executor], which are covered in
    [Loop Access and
    Inspection](../the-low-level-toolkit/loop-access-and-inspection.md) in [The
    Low-Level Toolkit](../the-low-level-toolkit/index.md).
    [`loop.run_in_executor()`][loop-run-in-executor] is the only built-in way
    to dispatch work to a [`ProcessPoolExecutor`][processpoolexecutor] from
    async code, so you will see it whenever CPU-bound offloading comes up.

A few things to note:

- [`loop.run_in_executor()`][loop-run-in-executor] requires the running loop,
  which you get with
  [`asyncio.get_running_loop()`][asyncio-get-running-loop].
- The executor is a [`ProcessPoolExecutor`][processpoolexecutor], not the
  default [`ThreadPoolExecutor`][threadpoolexecutor]. That is the key
  difference from [`asyncio.to_thread()`][asyncio-to-thread].
- Each function call and its arguments must be
  [picklable][picklable], because they are
  serialized and sent to a child process. Lambda functions, closures, and
  objects with unpicklable state will raise
  [`pickle.PicklingError`][picklingerror].
- The `#!py with ProcessPoolExecutor()` block shuts down the pool cleanly when
  the work is done. In a long-running service, you would typically create the
  pool once at startup and reuse it.

!!! Info

    Only reach for [`ProcessPoolExecutor`][processpoolexecutor] when the work
    is genuinely CPU-bound. Process creation and inter-process communication
    have significant overhead compared to threads. For I/O-bound blocking
    calls, [`asyncio.to_thread()`][asyncio-to-thread] is simpler and faster.

!!! Warning

    Python 3.14 adds [`InterpreterPoolExecutor`][interpreterpoolexecutor], but
    you should probably avoid it for now. Like
    [`ProcessPoolExecutor`][processpoolexecutor], it still serializes submitted
    callables, arguments, and return values, and have the same limitations as
    [`to_thread()`][asyncio-to-thread]. It also relies on your dependencies
    supporting multiple interpreters, and some third-party extension modules do
    not yet support that model. For now, prefer
    [`ProcessPoolExecutor`][processpoolexecutor] for CPU-bound work.

## When to Use What

Three rules of thumb:

1. **Prefer async libraries.** If you have a choice, use an async library that
   fits your needs.

2. **Default to [`asyncio.to_thread()`][asyncio-to-thread].** Most blocking
   code you encounter is I/O-bound. Thread overhead is low, there is no
   pickling requirement, and the API is a single function call.

3. **Reach for processes only when threads are not enough.** If you profile and
   find a CPU-bound function that still blocks the loop even with
   [`asyncio.to_thread()`][asyncio-to-thread], that is when you switch to
   [`ProcessPoolExecutor`][processpoolexecutor].

[await]: https://docs.python.org/3/reference/expressions.html#await
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[asyncio-to-thread]: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
[threadpoolexecutor]: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor
[loop-run-in-executor]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor
[threading-lock]: https://docs.python.org/3/library/threading.html#threading.Lock
[asyncio-lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[loop-call-soon-threadsafe]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon_threadsafe
[asyncio-get-running-loop]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop
[asyncio-queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[processpoolexecutor]: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ProcessPoolExecutor
[interpreterpoolexecutor]: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.InterpreterPoolExecutor
[picklable]: https://docs.python.org/3/library/pickle.html
[picklingerror]: https://docs.python.org/3/library/pickle.html#pickle.PicklingError
[threading]: https://docs.python.org/3/library/threading.html
[trio-to-thread-run-sync]: https://trio.readthedocs.io/en/stable/reference-core.html#trio.to_thread.run_sync
[official-tasks]: https://docs.python.org/3/library/asyncio-task.html
[official-event-loop]: https://docs.python.org/3/library/asyncio-eventloop.html
[official-dev]: https://docs.python.org/3/library/asyncio-dev.html
