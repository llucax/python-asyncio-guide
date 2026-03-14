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
cancellation make it much easier for cleanup to be skipped by accident.

A task can be cancelled at any [`await`][await], and if the resource's teardown
never runs, you get leaked connections, stuck locks, and file descriptors that
pile up until the OS complains. The good news: the tools for handling this are
straightforward, and if you follow a few rules you will never leak a resource.

## Async Context Managers and `#!py async with`

The [`async with` statement][async-with-statement] is the async equivalent of
the regular `#!py with` statement. It calls [`__aenter__()`][aenter] when the
block is entered and [`__aexit__()`][aexit] when it exits for async context
managers -- regardless of whether the exit is normal, an exception, or a
cancellation. Both methods are coroutines, so they can do async work like
sending a "close" message over the network or releasing a resource that
requires an [`await`][await].

One slightly less-common asyncio primitive is still a very good teaching
example here: [`asyncio.Lock`][asyncio-lock]. In task-based code you will
usually prefer message passing or single-task ownership over shared mutable
state, so locks are not as central as they are in threaded programs. But for
resource management, they make the contract of [`async with`][async-with] very
clear: acquiring may need an [`await`][await], and failing to release the lock
leaves other tasks stuck forever.

```python title="lock_demo.py" hl_lines="4"
import asyncio

async def increment(lock: asyncio.Lock, shared_data: dict[str, int]) -> None:
    async with lock: # (1)!
        value: int = shared_data["counter"]
        await asyncio.sleep(0.1)  # Simulate async work while the lock is held
        shared_data["counter"] = value + 1
        print(f"Incremented to {shared_data['counter']}")
    # (2)!

async def main() -> None:
    lock = asyncio.Lock()
    shared_data: dict[str, int] = {"counter": 0}

    async with asyncio.TaskGroup() as tg:
        for i in range(3):
            tg.create_task(increment(lock, shared_data), name=f"increment-{i}")

    print(f"Final count: {shared_data['counter']}")

if __name__ == "__main__":
    asyncio.run(main())
```

1. The `lock` is acquired here (awaiting for it to be released first if it was
   already taken), and then held for the whole `#!py async with` block.
2. The `lock` is released here, even if the body raised or was cancelled.

```text title="$ python lock_demo.py"
Incremented to 1
Incremented to 2
Incremented to 3
Final count: 3
```

The `#!py async with lock:` line acquires the lock when the block is entered
and releases it when the block exits. If a cancellation arrives while the body
is running, the [`CancelledError`][cancellederror] unwinds through the block,
[`__aexit__`][aexit] runs, and the lock is freed. No task is left waiting for
a lock that will never be released.

Do not over-read the example. In asyncio, locks are rarer than in threaded code
because tasks only switch at [`await`][await] points. This section uses
[`Lock`][asyncio-lock] because it makes the cleanup contract concrete. For the
actual "when should you reach for a lock?" decision, see [Advanced
Coordination](../beyond-the-basics/advanced-coordination.md).

You have already been using other async context managers too -- especially
[`asyncio.TaskGroup()`][taskgroup] and [`asyncio.timeout()`][asyncio-timeout].
The pattern is always the same: enter with [`async with`][async-with], and
cleanup is guaranteed on the way out.

!!! Warning

    If an API gives you an async context manager, **always** use it with
    [`async with`][async-with]. Calling [`__aenter__()`][aenter] and
    [`__aexit__()`][aexit] by hand is fragile and error-prone. The whole point
    of the protocol is that the [`async with`][async-with] statement guarantees
    [`__aexit__`][aexit] runs even when things go wrong.

## Ownership Boundaries

A resource must have exactly one *owner* -- the scope responsible for cleaning
it up. This is the same principle behind RAII in C++ or `#!py with` in
synchronous Python, extended to the async world.

The rule is simple: **the code that opens a resource is the code that closes
it.** A function that accepts a connection as a parameter should not close it;
that is the caller's job. A function that creates a connection must ensure it
is closed before returning, whether that return is normal, an exception, or a
cancellation.

This is why [`TaskGroup`][taskgroup] and [`async with`][async-with] compose so
well. The [`async with`][async-with] block is the owner scope: everything
created inside it is cleaned up when the block exits. A
[`TaskGroup`][taskgroup] guarantees all its children finish before
[`__aexit__`][aexit] runs, so resources opened inside the group are still valid
for the entire lifetime of the children.

```python
async def process_batch(urls: list[str]) -> None:
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            tg.create_task(fetch(url), name=f"fetch-{url}")
    # All tasks done, all resources they used are safe to clean up
```

When you find yourself passing a resource across multiple scopes without a
clear owner, stop and restructure. The resource should live in an [`async
with`][async-with] block, and every piece of code that uses it should be a
child of that scope.

## Async Iterators and `#!py async for`

The [`async for` statement][async-for-statement] iterates over an *asynchronous
iterable* -- any object that implements [`__aiter__()`][aiter] and
[`__anext__()`][anext]. They are commonly called *streams* too.

There is not much ceremony -- `#!py async for` works just like regular `for`,
but each iteration step can [`await`][await]:

```python
async for item in some_async_source:
    process(item)
```

This roughly translates to:

```python
iterator = some_async_source.__aiter__()
while True:
    try:
        item = await iterator.__anext__()
    except StopAsyncIteration:
        break
    process(item)
```

The loop calls [`__anext__()`][anext] before each iteration, which is a
coroutine that may suspend while waiting for the next item. When the iterable
is exhausted, it raises `StopAsyncIteration` and the loop ends.

## Async Generators

An *async generator* is an async function that uses `#!py yield` instead of (or
in addition to) `#!py return` (the result is *async iteratable*). Just as
regular generators produce values lazily, async generators produce values
lazily with [`await`][await] between yields:

```python title="async_gen_basic.py" hl_lines="4 7"
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

```text title="$ python async_gen_basic.py"
T-minus 3
T-minus 2
T-minus 1
Liftoff!
```

This looks clean, but async generators have a subtle and dangerous cleanup
problem. Consider a generator that holds a resource:

```python title="async_gen_leak.py" hl_lines="5 11"
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

```text title="$ python async_gen_leak.py"
Opening resource
line 0
line 1
line 2
Stopping early!
Closing resource
Done
```

In this simple case, Python's garbage collector eventually finalises the
generator and the `#!py finally` block runs. But "eventually" is not a
guarantee you can rely on. If the generator is abandoned due to cancellation,
or if the garbage collector is delayed, the `#!py finally` block may run much
later -- or in a context where it can no longer do async cleanup properly. In a
long-running server, this means leaked connections and file descriptors.

!!! Danger

    Never rely on the garbage collector to clean up async generators. The `#!py
    finally` block may run, but the *timing* is unpredictable and async
    operations inside it may fail or be silently skipped. Always close async
    generators explicitly.

## `contextlib.aclosing()`

[`contextlib.aclosing()`][contextlib-aclosing] is the fix. It wraps an async
generator (or any object with an [`aclose()`][aclose] method) in an async
context manager that guarantees [`aclose()`][aclose] is called when the block
exits:

```python title="async_gen_safe.py" hl_lines="15"
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

```text title="$ python async_gen_safe.py"
Opening resource
line 0
line 1
line 2
Stopping early!
Closing resource
Done
```

The output looks the same, but the behaviour is fundamentally different. With
`#!py aclosing()`, the generator's [`aclose()`][aclose] method is called
*immediately* when the [`async with`][async-with] block exits -- not at some
unpredictable later time by the garbage collector. The `#!py finally` block
inside the generator runs promptly, and any async cleanup it needs to do
happens in the right context.

!!! Danger

    `#!py async for` does **not** automatically close the iterable when the
    loop exits early (via `#!py break` or exception).

    **Always wrap async generators in `#!py aclosing()` when you consume
    them.** If you iterate to completion you don't strictly need it, but
    applying it consistently means you never have to think about whether early
    exit is possible.

!!! Tip "Trio"

    [Trio][trio-docs] requires [`trio.aclosing()`][trio-aclosing] for every
    async generator iteration and will warn you loudly if you forget. asyncio
    is more lenient at runtime, but the same discipline applies.

## Async Cleanup

`#!py async with` and `#!py finally` blocks guarantees that cleanup code runs.
It does not guarantee that every awaited cleanup step is worth waiting for
forever, or waiting at all.

If you need to call an async function to clean up, it is recommended to use a
bounded timeout for functions that could hanging indefinitely (like closing a
socket connection).

```python
finally:
    try:
        async with asyncio.timeout(1):
            await resource.aclose()
    except TimeoutError:
        print("closing the resource timed out")
```

If teardown has both a synchronous "start shutting down" step and an awaited
"wait until shutdown finishes" step, you can use a timeout for the async part.
For example:

```python
finally:
    writer.close()
    try:
        async with asyncio.timeout(1):
            await writer.wait_closed()
    except TimeoutError:
        print("writer close timed out")
```

Or, in some cases it could even make sense to skip the wait entirely inside a
`#!py finally` block:

```python
finally:
    writer.close()
```

!!! Warning

    Keep cleanup code fast and simple -- closing a socket, releasing a lock,
    writing a short log message. Do **not** start a 30-second retry loop or a
    complex multi-step protocol in a `#!py finally` block. If your cleanup
    itself needs to [`await`][await] something slow, the outer timeout or
    cancellation scope may not account for that extra time, and the program's
    shutdown behaviour becomes unpredictable.

!!! Tip "Trio"

    The same rule applies in [Trio][trio-docs]. [Trio][trio-docs] enforces it
    more strictly with [cancel scope][trio-cancel-scope] semantics -- by
    default, awaited cleanup inside a cancelled scope is still under
    cancellation pressure. asyncio is more lenient, but the principle is the
    same: keep cleanup quick, and treat any extra await in teardown as a
    deliberate choice.

### Async Context Managers and Async Cleanup

For async context managers, it is generally not possible to use timeouts or
shielding, as we can't easily capture only the cleanup part.

The `#!py async with x: do(x)` statement translates to:

```python
await x.__aenter__()
try:
    do(x)
finally:
    await x.__aexit__(...)
```

If you need to add a timeout to the cleanup under cancellation, you will
need to use the `try`/`finally` explicitly.

In general, libraries providing async context managers should have this in
mind and try to do *the right thing by default*, but you should be aware of
this when using async context managers, and get to know what their `#!py
__aexit__()` does, and if it really makes `#!py async` calls or not (many
don't).

### Async Cleanup Cancellation

Note that a second cancellation request can cancel the cleanup itself!

For example, a second, higher-level timout. In these cases, if interruption
would leave the system in a worse state -- for example, a commit, rollback, or
protocol close frame, best-effort cleanup is not enough. In those cases
[`asyncio.shield()`][asyncio-shield] may be appropriate, but
[Shielding](../beyond-the-basics/shielding.md) is a more advanced topic, so
we'll cover it later.

## Putting It Together

Here is a small example that combines everything from this section: an async
generator that produces items from a simulated resource, proper cleanup with
`#!py aclosing()`, and concurrent consumers managed by a
[`TaskGroup`][taskgroup].

```python title="resource_pipeline.py"
import asyncio
from contextlib import aclosing
from collections.abc import AsyncGenerator, AsyncIterator

async def event_stream(name: str, count: int) -> AsyncGenerator[str, None]:
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
    print(f"[{name}] Starting consumer for {limit} events")
    async for event in stream:
        print(f"  [{name}] got {event}")
        collected.append(event)
        if len(collected) >= limit:
            break
    return collected

async def main() -> None:
    async with ( # (1)!
        aclosing(event_stream("A", 10)) as stream_a,
        aclosing(event_stream("B", 10)) as stream_b,
    ):
        async with asyncio.TaskGroup() as tg:
            t1: asyncio.Task[list[str]] = tg.create_task(
                consumer("fast", stream_a, limit=2),
                name="fast-consumer",
            )
            t2: asyncio.Task[list[str]] = tg.create_task(
                consumer("slow", stream_b, limit=3),
                name="slow-consumer",
            )

    print(f"\nfast collected: {t1.result()}")
    print(f"slow collected: {t2.result()}")

if __name__ == "__main__":
    asyncio.run(main())
```

1. Order is important here, we need to make sure the generators are only closed
   after all taks finished, so after the `TaskGroup` block ends.

```text title="$ python resource_pipeline.py"
[fast] Starting consumer for 2 events
[A] Stream opened
[slow] Starting consumer for 3 events
[B] Stream opened
  [fast] got A/event-0
  [slow] got B/event-0
  [fast] got A/event-1
  [slow] got B/event-1
  [slow] got B/event-2
[B] Stream closed
[A] Stream closed

fast collected: ['A/event-0', 'A/event-1']
slow collected: ['B/event-0', 'B/event-1', 'B/event-2']
```

Both consumers stop early (before the stream is exhausted), but `#!py
aclosing()` ensures each stream's `#!py finally` block runs immediately. The
[`TaskGroup`][taskgroup] guarantees both consumers finish before `#!py main()`
continues. Every resource has a clear owner, every cleanup path is covered, and
cancellation would not change any of that -- the [`async with`][async-with]
blocks and `#!py finally` blocks would still run.

[async-with]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[await]: https://docs.python.org/3/reference/expressions.html#await
[async-with-statement]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[aenter]: https://docs.python.org/3/reference/datamodel.html#object.__aenter__
[aexit]: https://docs.python.org/3/reference/datamodel.html#object.__aexit__
[asyncio-lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[asyncio-shield]: https://docs.python.org/3/library/asyncio-task.html#asyncio.shield
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[timeouterror]: https://docs.python.org/3/library/exceptions.html#TimeoutError
[asyncio-timeout-at]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout_at
[trio-docs]: https://trio.readthedocs.io/en/stable/
[trio-cancel-scope]: https://trio.readthedocs.io/en/stable/reference-core.html#cancellation-and-timeouts
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[contextlib-aclosing]: https://docs.python.org/3/library/contextlib.html#contextlib.aclosing
[aclose]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack.aclose
[trio-aclosing]: https://trio.readthedocs.io/en/stable/reference-core.html#trio.aclosing
[async-for-statement]: https://docs.python.org/3/reference/compound_stmts.html#async-for
[aiter]: https://docs.python.org/3/reference/datamodel.html#object.__aiter__
[anext]: https://docs.python.org/3/reference/datamodel.html#object.__anext__
