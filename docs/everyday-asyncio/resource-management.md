---
title: Resource Management
description: >-
  Learn to manage async resources safely with async with, try/finally,
  contextlib.aclosing(), and async generators. Prevent leaked connections,
  stuck locks, and file descriptor exhaustion under cancellation.
---

# Resource Management

Async code opens connections, acquires locks, and allocates resources that need
cleanup -- just like synchronous code. The difference is that concurrency and
cancellation make it much easier for cleanup to be skipped by accident. A task
can be cancelled at any `await`, and if the resource's teardown never runs,
you get leaked connections, stuck locks, and file descriptors that pile up
until the OS complains. The good news: the tools for handling this are
straightforward, and if you follow a few rules you will never leak a resource.

## `async with`

The
[`async with` statement](https://docs.python.org/3/reference/compound_stmts.html#async-with)
is the async equivalent of the regular `with` statement. It calls
[`__aenter__()`](https://docs.python.org/3/reference/datamodel.html#object.__aenter__)
when the block is entered and
[`__aexit__()`](https://docs.python.org/3/reference/datamodel.html#object.__aexit__)
when it exits -- regardless of whether the exit is normal, an exception, or a
cancellation. Both methods are coroutines, so they can do async work like
sending a "close" message over the network or releasing a resource that
requires an `await`.

The canonical example is
[`asyncio.Lock`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock).
Acquiring it requires an `await` (another task might be holding it), and
releasing it must happen exactly once:

```python
# lock_demo.py
import asyncio

async def increment(lock: asyncio.Lock, counter: dict[str, int]) -> None:
    async with lock:
        # Lock is held for this block
        value: int = counter["n"]
        await asyncio.sleep(0.1)  # Simulate async work
        counter["n"] = value + 1
        print(f"Incremented to {counter['n']}")
    # Lock is released here, even if the body raised or was cancelled

async def main() -> None:
    lock = asyncio.Lock()
    counter: dict[str, int] = {"n": 0}

    async with asyncio.TaskGroup() as tg:
        for _ in range(3):
            tg.create_task(increment(lock, counter))

    print(f"Final count: {counter['n']}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python lock_demo.py
Incremented to 1
Incremented to 2
Incremented to 3
Final count: 3
```

The `async with lock:` line acquires the lock (`__aenter__`), and when the
block exits -- for any reason -- it is released (`__aexit__`). If a
cancellation arrives while the body is running, the `CancelledError` unwinds
through the block, `__aexit__` runs, and the lock is freed. No task is left
waiting forever for a lock that will never be released.

You have already been using `async with` throughout this chapter:
`asyncio.TaskGroup()`, `asyncio.timeout()`, and `asyncio.timeout_at()` are all
async context managers. The pattern is always the same -- enter with
`async with`, and the cleanup is guaranteed.

!!! warning

    If an API gives you an async context manager, **always** use it with
    `async with`. Calling `__aenter__()` and `__aexit__()` by hand is fragile
    and error-prone. The whole point of the protocol is that the `async with`
    statement guarantees `__aexit__` runs even when things go wrong.

## Cleanup Under Cancellation

The previous section introduced `try`/`finally` for cleanup when a coroutine
is cancelled. Let's go deeper with a resource-oriented example. Imagine an
async connection that must be explicitly closed:

```python
# cleanup_under_cancel.py
import asyncio

class FakeConnection:
    """Simulates an async connection with explicit open/close."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def open(self) -> None:
        print(f"[{self.name}] Connection opened")

    async def close(self) -> None:
        print(f"[{self.name}] Connection closed")

    async def query(self, sql: str) -> str:
        await asyncio.sleep(5)  # Simulate slow query
        return f"Results for: {sql}"

async def do_work() -> None:
    conn = FakeConnection("db")
    await conn.open()
    try:
        result: str = await conn.query("SELECT * FROM users")
        print(result)
    finally:
        await conn.close()

async def main() -> None:
    try:
        async with asyncio.timeout(1):
            await do_work()
    except TimeoutError:
        print("Timed out, but connection was still closed")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python cleanup_under_cancel.py
[db] Connection opened
[db] Connection closed
Timed out, but connection was still closed
```

The timeout fires after one second, cancelling the `await conn.query()` call.
The `CancelledError` unwinds the `try` block, the `finally` block runs, and
the connection is closed properly. This is exactly the behaviour you want.

!!! warning

    Cleanup code in `finally` blocks runs while the task is being cancelled.
    Keep it fast and simple -- closing a socket, releasing a lock, writing a
    short log message. Do **not** start a 30-second retry loop or a complex
    multi-step protocol in a `finally` block. If your cleanup itself needs to
    `await` something slow, the outer timeout or cancellation scope may not
    account for that extra time, and the program's shutdown behaviour becomes
    unpredictable.

!!! tip "Trio users"

    The same rule applies in Trio. Trio enforces it more
    strictly with *cancel shielding* semantics -- by default, cancelled tasks
    cannot start new I/O in their cleanup path. asyncio is more lenient, but
    the principle is the same: cleanup should be quick.

## Ownership Boundaries

A resource must have exactly one *owner* -- the scope responsible for cleaning
it up. This is the same principle behind RAII in C++ or `with` in synchronous
Python, extended to the async world.

The rule is simple: **the code that opens a resource is the code that closes
it.** A function that accepts a connection as a parameter should not close it;
that is the caller's job. A function that creates a connection must ensure it
is closed before returning, whether that return is normal, an exception, or a
cancellation.

This is why `TaskGroup` and `async with` compose so well. The `async with`
block is the owner scope: everything created inside it is cleaned up when the
block exits. A `TaskGroup` guarantees all its children finish before
`__aexit__` runs, so resources opened inside the group are still valid for the
entire lifetime of the children.

```python
async def process_batch(urls: list[str]) -> None:
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            tg.create_task(fetch(url))
    # All tasks done, all resources they used are safe to clean up
```

When you find yourself passing a resource across multiple scopes without a
clear owner, stop and restructure. The resource should live in an
`async with` block, and every piece of code that uses it should be a child of
that scope.

## Async Generators

An *async generator* is an async function that uses `yield` instead of (or in
addition to) `return`. Just as regular generators produce values lazily, async
generators produce values lazily with `await` between yields:

```python
# async_gen_basic.py
import asyncio
from collections.abc import AsyncIterator

async def countdown(n: int) -> AsyncIterator[int]:
    for i in range(n, 0, -1):
        await asyncio.sleep(0.5)
        yield i

async def main() -> None:
    async for value in countdown(3):
        print(f"T-minus {value}")
    print("Liftoff!")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python async_gen_basic.py
T-minus 3
T-minus 2
T-minus 1
Liftoff!
```

This looks clean, but async generators have a subtle and dangerous cleanup
problem. Consider a generator that holds a resource:

```python
# async_gen_leak.py
import asyncio
from collections.abc import AsyncIterator

async def read_lines() -> AsyncIterator[str]:
    print("Opening resource")
    try:
        for i in range(100):
            await asyncio.sleep(0.1)
            yield f"line {i}"
    finally:
        print("Closing resource")  # Will this run?

async def main() -> None:
    async for line in read_lines():
        print(line)
        if line == "line 2":
            print("Stopping early!")
            break

    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python async_gen_leak.py
Opening resource
line 0
line 1
line 2
Stopping early!
Closing resource
Done
```

In this simple case, Python's garbage collector eventually finalises the
generator and the `finally` block runs. But "eventually" is not a guarantee
you can rely on. If the generator is abandoned due to cancellation, or if the
garbage collector is delayed, the `finally` block may run much later -- or in
a context where it can no longer do async cleanup properly. In a long-running
server, this means leaked connections and file descriptors.

!!! danger

    Never rely on the garbage collector to clean up async generators. The
    `finally` block may run, but the *timing* is unpredictable and async
    operations inside it may fail or be silently skipped. Always close async
    generators explicitly.

## `contextlib.aclosing()`

[`contextlib.aclosing()`](https://docs.python.org/3/library/contextlib.html#contextlib.aclosing)
is the fix. It wraps an async generator (or any object with an `aclose()`
method) in an async context manager that guarantees `aclose()` is called when
the block exits:

```python
# async_gen_safe.py
import asyncio
from contextlib import aclosing
from collections.abc import AsyncIterator

async def read_lines() -> AsyncIterator[str]:
    print("Opening resource")
    try:
        for i in range(100):
            await asyncio.sleep(0.1)
            yield f"line {i}"
    finally:
        print("Closing resource")

async def main() -> None:
    async with aclosing(read_lines()) as lines:
        async for line in lines:
            print(line)
            if line == "line 2":
                print("Stopping early!")
                break

    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python async_gen_safe.py
Opening resource
line 0
line 1
line 2
Stopping early!
Closing resource
Done
```

The output looks the same, but the behaviour is fundamentally different.
With `aclosing()`, the generator's `aclose()` method is called *immediately*
when the `async with` block exits -- not at some unpredictable later time by
the garbage collector. The `finally` block inside the generator runs promptly,
and any async cleanup it needs to do happens in the right context.

!!! tip

    The rule is simple: **always wrap async generators in `aclosing()` when you
    consume them.** If you iterate to completion you don't strictly need it, but
    applying it consistently means you never have to think about whether early
    exit is possible.

!!! tip "Trio users"

    Trio requires `aclosing()` for every async generator
    iteration and will warn you loudly if you forget. asyncio is more lenient at
    runtime, but the same discipline applies.

## `async for`

The
[`async for` statement](https://docs.python.org/3/reference/compound_stmts.html#async-for)
iterates over an *asynchronous iterable* -- any object that implements
[`__aiter__()`](https://docs.python.org/3/reference/datamodel.html#object.__aiter__)
and
[`__anext__()`](https://docs.python.org/3/reference/datamodel.html#object.__anext__).
Async generators are the most common source of async iterables, but you will
encounter them elsewhere too: network streams, database cursors, message
queues, and any API that delivers items one at a time over I/O.

There is not much ceremony -- `async for` works just like regular `for`, but
each iteration step can `await`:

```python
async for item in some_async_source:
    process(item)
```

The loop calls `__anext__()` before each iteration, which is a coroutine that
may suspend while waiting for the next item. When the iterable is exhausted,
it raises `StopAsyncIteration` and the loop ends.

!!! note

    `async for` does **not** automatically close the iterable when the loop
    exits early (via `break` or exception). That is why `aclosing()` is
    necessary for async generators -- it provides the cleanup that `async for`
    does not.

## Putting It Together

Here is a small example that combines everything from this section: an async
generator that produces items from a simulated resource, proper cleanup with
`aclosing()`, and concurrent consumers managed by a `TaskGroup`.

```python
# resource_pipeline.py
import asyncio
from contextlib import aclosing
from collections.abc import AsyncIterator

async def event_stream(name: str, count: int) -> AsyncIterator[str]:
    """Simulate an async event source that requires cleanup."""
    print(f"[{name}] Stream opened")
    try:
        for i in range(count):
            await asyncio.sleep(0.3)
            yield f"{name}/event-{i}"
    finally:
        print(f"[{name}] Stream closed")

async def consumer(name: str, stream: AsyncIterator[str], limit: int) -> list[str]:
    """Consume up to `limit` events from a stream."""
    collected: list[str] = []
    async with aclosing(stream) as events:
        async for event in events:
            print(f"  [{name}] got {event}")
            collected.append(event)
            if len(collected) >= limit:
                break
    return collected

async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(
            consumer("fast", event_stream("A", 10), limit=2)
        )
        t2 = tg.create_task(
            consumer("slow", event_stream("B", 10), limit=3)
        )

    print(f"\nfast collected: {t1.result()}")
    print(f"slow collected: {t2.result()}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python resource_pipeline.py
[A] Stream opened
[B] Stream opened
  [fast] got A/event-0
  [slow] got B/event-0
  [fast] got A/event-1
  [slow] got B/event-1
[A] Stream closed
  [slow] got B/event-2
[B] Stream closed

fast collected: ['A/event-0', 'A/event-1']
slow collected: ['B/event-0', 'B/event-1', 'B/event-2']
```

Both consumers stop early (before the stream is exhausted), but `aclosing()`
ensures each stream's `finally` block runs immediately. The `TaskGroup`
guarantees both consumers finish before `main()` continues. Every resource has
a clear owner, every cleanup path is covered, and cancellation would not change
any of that -- the `async with` blocks and `finally` blocks would still run.

---
