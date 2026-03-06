---
title: Futures
description: >-
  Create and resolve bare asyncio futures with loop.create_future(), bridge
  concurrent.futures with asyncio.wrap_future(), and glue callback-based
  code into the async world for library and framework development.
---

# Futures

Chapter 3 covered [what futures are](../how-asyncio-works/tasks-and-futures.md):
passive containers for a value that doesn't exist yet. You know the API --
`.done()`, `.result()`, `.set_result()`, `await`. This section is about
*using* them in practice: creating them, resolving them manually, and bridging
them with `concurrent.futures`. These are the tools you reach for when you're
building a library or framework that needs to glue callback-based code into the
async world.

!!! note

    If you are writing application code, you almost certainly don't need
    bare futures. Tasks,
    [task groups](../everyday-asyncio/concurrent-tasks.md), and
    [streams](../everyday-asyncio/streams.md) cover the vast majority
    of use cases. This material is for library authors who are building
    abstractions on top of asyncio's low-level machinery.

## `loop.create_future()`

The right way to create a bare future is
[`loop.create_future()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_future).
It returns an empty `asyncio.Future` bound to the running loop:

```python title="create_future_demo.py"
import asyncio


async def main() -> None:
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[int] = loop.create_future()

    print(f"pending: {not fut.done()}")  # True -- nothing set yet

    fut.set_result(42)

    print(f"done:    {fut.done()}")      # True
    print(f"result:  {fut.result()}")    # 42

    # You can also await a future that is already resolved.
    value: int = await fut
    print(f"awaited: {value}")           # 42


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python create_future_demo.py"
pending: True
done:    True
result:  42
awaited: 42
```

Why `loop.create_future()` instead of `asyncio.Future()`? Two reasons. First,
it's faster -- the loop can return an optimized C implementation. Second, it
binds the future to the correct loop automatically, which avoids subtle bugs
when multiple loops are involved (testing, embedded event loops). Always use
`create_future()`.

!!! warning

    A future can only be resolved once. Calling `set_result()` or
    `set_exception()` on a future that is already done raises
    [`asyncio.InvalidStateError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.InvalidStateError).

## Wrapping Callback-Based APIs

This is the classic use case. You have a library that reports results through
callbacks, and you want to `await` it from a coroutine. The pattern is always
the same:

1. Create a future.
2. Pass a callback that resolves the future.
3. `await` the future.

Here is a concrete example. Imagine a legacy sensor library that reads a value
asynchronously and calls you back with the result:

```python title="callback_bridge.py"
import asyncio
from typing import Callable


# --- Simulated callback-based library ---

def read_sensor(callback: Callable[[float], None]) -> None:
    """Simulates an async sensor read that reports via callback."""
    loop = asyncio.get_running_loop()
    # In reality this might be a C library, a hardware driver, etc.
    loop.call_later(0.5, callback, 23.7)


# --- The bridge ---

async def read_sensor_async() -> float:
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[float] = loop.create_future()

    def on_reading(value: float) -> None:
        if not fut.done():
            fut.set_result(value)

    read_sensor(on_reading)
    return await fut


# --- Application code ---

async def main() -> None:
    reading: float = await read_sensor_async()
    print(f"Sensor reading: {reading}°C")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python callback_bridge.py"
Sensor reading: 23.7°C
```

The `if not fut.done()` guard in the callback is defensive -- it prevents a
double-resolution crash if the callback fires more than once. In most cases
the guard won't trigger, but it costs nothing and saves you from hard-to-debug
`InvalidStateError` exceptions in production.

This pattern works for any callback-based API: GUI event handlers, hardware
drivers, notification systems, custom protocol libraries. The future acts as a
one-shot bridge between "someone will call this function later" and "I want to
`await` a result now."

## `asyncio.wrap_future()`

Sometimes you're not dealing with a raw callback -- you already have a
[`concurrent.futures.Future`](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future)
from a `ThreadPoolExecutor` or `ProcessPoolExecutor`. These are *not* the same
as `asyncio.Future` -- you can't `await` them directly. But
[`asyncio.wrap_future()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.wrap_future)
converts one into the other:

```python title="wrap_future_demo.py"
import asyncio
from concurrent.futures import ThreadPoolExecutor


def heavy_computation(n: int) -> int:
    """A blocking function that runs in a thread."""
    total: int = 0
    for i in range(n):
        total += i * i
    return total


async def main() -> None:
    executor = ThreadPoolExecutor(max_workers=2)

    # Submit work to the thread pool -- returns concurrent.futures.Future
    cf_future = executor.submit(heavy_computation, 1_000_000)

    # Wrap it so we can await it in asyncio
    result: int = await asyncio.wrap_future(cf_future)
    print(f"Result: {result}")

    executor.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python wrap_future_demo.py"
Result: 333332833333500000
```

`wrap_future()` creates an `asyncio.Future`, wires up a done callback on the
`concurrent.futures.Future` so that when the thread finishes, the asyncio
future gets resolved -- and it does this thread-safely via
`loop.call_soon_threadsafe()`. You get a clean `await`-able handle into work
that is running on a completely different thread.

!!! tip

    If you control the submission, prefer
    [`asyncio.to_thread()`](../beyond-the-basics/blocking-code.md)
    or
    [`loop.run_in_executor()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor)
    -- they handle the wrapping for you. `wrap_future()` is for when
    someone *else* handed you a `concurrent.futures.Future` and you need to
    integrate it into your async code. A third-party job queue, a shared
    executor managed by another subsystem, a legacy API that returns
    futures -- those are the cases where `wrap_future()` shines.

## Error Propagation

The error side mirrors the happy path. Use
[`future.set_exception()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_exception)
to resolve a future with an error, and `await` will re-raise it at the call
site:

```python title="future_error.py"
import asyncio
from typing import Callable


def flaky_read(callback: Callable[[float], None],
               errback: Callable[[Exception], None]) -> None:
    """Simulates a read that fails."""
    loop = asyncio.get_running_loop()
    loop.call_later(0.3, errback, ConnectionError("sensor disconnected"))


async def flaky_read_async() -> float:
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[float] = loop.create_future()

    def on_success(value: float) -> None:
        if not fut.done():
            fut.set_result(value)

    def on_error(exc: Exception) -> None:
        if not fut.done():
            fut.set_exception(exc)

    flaky_read(on_success, on_error)
    return await fut


async def main() -> None:
    try:
        value: float = await flaky_read_async()
        print(f"Got: {value}")
    except ConnectionError as exc:
        print(f"Read failed: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python future_error.py"
Read failed: sensor disconnected
```

The `set_exception()` call stores the exception inside the future. When you
`await` it, the exception is re-raised as if it happened at the `await` line.
This means normal `try`/`except` works exactly as you'd expect -- the error
propagates through the same channels as any other async exception.

The same `if not fut.done()` guard applies here. If both a success callback
and an error callback could fire (race conditions in some libraries), the
guard ensures only the first one resolves the future.

!!! danger

    Never pass a `BaseException` subclass (like `KeyboardInterrupt` or
    `SystemExit`) to `set_exception()`. It raises a `TypeError`. These are
    not meant to flow through futures -- they are process-level signals
    that bypass normal exception handling.

## Summary

Futures are plumbing. They are the lowest-level primitive for representing "a
value that will exist later," and they are what asyncio's internals -- tasks,
transports, protocols -- are built on top of.

In practice, you need them in exactly two situations:

- **Bridging callbacks.** You have a callback-based API and want an
  `await`-able interface. Create a future, resolve it from the callback, return
  it to the caller.
- **Bridging threads.** You have a `concurrent.futures.Future` from a thread
  pool and want to `await` it. Call `asyncio.wrap_future()`.

For everything else -- running coroutines concurrently, collecting results,
handling cancellation -- use tasks and task groups. They are futures under the
hood, but they handle the lifecycle management that you would otherwise have to
do yourself.
