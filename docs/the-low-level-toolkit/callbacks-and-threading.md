---
title: Callbacks and Threading
description: >-
  Bridge threads and the asyncio event loop with done callbacks,
  call_soon_threadsafe(), run_coroutine_threadsafe(), and signal handling.
  Schedule async work from synchronous threads safely.
---

# Callbacks and Threading

Chapter 2 covered
[`asyncio.to_thread()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread)
-- the way to call blocking code *from* an async context. But sometimes the
boundary runs the other direction. You have a thread -- maybe a web framework's
request handler, a GUI event loop, or a monitoring watchdog -- and it needs to
reach *into* the asyncio event loop to schedule work or collect results. That
requires a different set of tools: done callbacks, thread-safe scheduling,
coroutine submission from non-async threads, and signal handling.

## `add_done_callback()` and `remove_done_callback()`

Every
[`asyncio.Future`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future)
(and every
[`asyncio.Task`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task),
which is a subclass) supports *done callbacks* -- plain functions that fire
when the future completes. You saw the API listed in
[Tasks and Futures](../how-asyncio-works/tasks-and-futures.md); here is how
you actually use it.

The callback receives the future as its only argument. You can inspect it to
get the result, the exception, or check if it was cancelled:

```python
# done_callback.py
import asyncio


def on_complete(fut: asyncio.Future[str]) -> None:
    if fut.cancelled():
        print("task was cancelled")
    elif fut.exception() is not None:
        print(f"task failed: {fut.exception()}")
    else:
        print(f"task succeeded: {fut.result()}")


async def do_work() -> str:
    await asyncio.sleep(0.5)
    return "all good"


async def main() -> None:
    task: asyncio.Task[str] = asyncio.create_task(do_work(), name="worker")
    task.add_done_callback(on_complete)
    await task


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python done_callback.py
task succeeded: all good
```

A few things to know:

- **The callback is a plain `def`, not `async def`.** It is scheduled via
  [`call_soon()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon),
  so it runs on the event loop thread in the next iteration of the loop --
  *not* in a separate thread. Keep it fast. If you need to do real work in
  response to completion, have the callback schedule a new task.

- **You can attach multiple callbacks** -- they fire in the order added.
  [`future.remove_done_callback(fn)`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.remove_done_callback)
  removes a callback and returns the count removed (the same function can be
  added more than once).

- **If the future is already done when you add the callback, it still fires**
  -- on the next loop iteration, via `call_soon()`.

!!! note

    Done callbacks are the low-level mechanism that makes `await task`
    work. The task pseudocode in
    [Chapter 3](../how-asyncio-works/tasks-and-futures.md) showed how a
    task registers `__step` as a done callback on the future it is
    awaiting. You rarely need done callbacks yourself -- `await` is almost
    always cleaner -- but they are indispensable in library code that must
    react to completion without suspending.

## `call_soon_threadsafe()`

[`loop.call_soon_threadsafe()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon_threadsafe)
is the thread-safe variant of `call_soon()`. It schedules a callback on the
event loop from *any* thread. The regular `call_soon()` is not thread-safe --
calling it from a background thread can corrupt internal data structures.
`call_soon_threadsafe()` uses proper synchronization and wakes the loop's
selector so the callback runs promptly, even if the loop is blocked on I/O.

Chapter 2's [Blocking Code](../beyond-the-basics/blocking-code.md) section
introduced this briefly. Here is a fuller example -- a background thread that
sends progress updates to the event loop:

```python
# threadsafe_progress.py
import asyncio
import threading
import time


def background_worker(
    loop: asyncio.AbstractEventLoop, progress: list[int],
) -> None:
    """Runs in a plain thread. Reports progress to the event loop."""
    for i in range(1, 6):
        time.sleep(0.3)  # simulate slow work
        loop.call_soon_threadsafe(progress.append, i * 20)
    loop.call_soon_threadsafe(progress.append, -1)  # sentinel: done


async def main() -> None:
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    progress: list[int] = []

    thread = threading.Thread(
        target=background_worker, args=(loop, progress), daemon=True
    )
    thread.start()

    # Poll until the sentinel arrives.
    while True:
        await asyncio.sleep(0.1)
        while progress:
            value: int = progress.pop(0)
            if value == -1:
                print("background work complete")
                thread.join()
                return
            print(f"progress: {value}%")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python threadsafe_progress.py
progress: 20%
progress: 40%
progress: 60%
progress: 80%
progress: 100%
background work complete
```

!!! warning

    `call_soon_threadsafe()` only schedules *plain callbacks* -- regular
    functions with positional arguments. You cannot pass a coroutine to it.
    If you need to schedule a coroutine from another thread, use
    `run_coroutine_threadsafe()` (next section).

## `run_coroutine_threadsafe()`

[`asyncio.run_coroutine_threadsafe()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.run_coroutine_threadsafe)
is the big one. It takes a coroutine and a running event loop, schedules it as
a task on that loop, and returns a
[`concurrent.futures.Future`](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future)
-- *not* an `asyncio.Future` -- that the calling thread can block on.

This is the tool you reach for when a synchronous thread needs to call async
code and wait for the result. The classic scenario: you have an async service
layer and a synchronous handler that needs to call into it.

```python
# run_coro_threadsafe.py
import asyncio
import concurrent.futures
import threading


async def async_lookup(key: str) -> str:
    """Pretend this hits an async database."""
    await asyncio.sleep(0.5)
    return f"value-for-{key}"


def sync_handler(loop: asyncio.AbstractEventLoop) -> None:
    """Runs in a worker thread -- calls async code from sync context."""
    thread_name: str = threading.current_thread().name
    print(f"[{thread_name}] submitting coroutine to event loop")

    # Schedule the coroutine on the event loop.
    coro = async_lookup("user-42")
    cf_future: concurrent.futures.Future[str] = (
        asyncio.run_coroutine_threadsafe(coro, loop)
    )

    # Block this thread until the result is ready.
    result: str = cf_future.result(timeout=5.0)
    print(f"[{thread_name}] got result: {result}")


async def main() -> None:
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    # Spawn several sync handlers in threads.
    threads: list[threading.Thread] = [
        threading.Thread(target=sync_handler, args=(loop,), name=f"worker-{i}")
        for i in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        await asyncio.to_thread(t.join)

    print("all handlers complete")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python run_coro_threadsafe.py
[worker-0] submitting coroutine to event loop
[worker-1] submitting coroutine to event loop
[worker-2] submitting coroutine to event loop
[worker-0] got result: value-for-user-42
[worker-1] got result: value-for-user-42
[worker-2] got result: value-for-user-42
all handlers complete
```

Key details:

- The returned object is a `concurrent.futures.Future` with a blocking
  `.result(timeout=...)` method. Safe to call from a thread -- *not* from the
  event loop thread (that would deadlock).

- If the coroutine raises, `cf_future.result()` re-raises it in the calling
  thread. You can also call `cf_future.cancel()` to cancel the underlying
  asyncio task.

!!! warning

    You need a *running* event loop to use
    `run_coroutine_threadsafe()`. It does not start one for you. The
    typical pattern is to start the loop in a dedicated thread (or with
    `asyncio.run()` in the main thread) and pass the loop object to any
    sync threads that need it.

## Signal Handling

Long-running async programs -- servers, daemons, pipelines -- need to respond
to Unix signals for graceful shutdown.
[`loop.add_signal_handler()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.add_signal_handler)
registers a callback that the event loop invokes when a signal arrives. Unlike
[`signal.signal()`](https://docs.python.org/3/library/signal.html#signal.signal),
the asyncio variant is loop-safe -- the callback runs via `call_soon()` in the
loop thread, not in a signal-handler context.

The [Shutdown Sequence](../how-asyncio-works/shutdown-sequence.md) section
mentioned that signal handling belongs here. The recommended pattern is to set
an [`asyncio.Event`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event)
when the signal arrives and have your main code wait on that event:

```python
# graceful_shutdown.py
import asyncio
import signal


async def run_server(shutdown: asyncio.Event) -> None:
    """Simulate a server that runs until told to stop."""
    print("server: running (send SIGINT or SIGTERM to stop)")
    await shutdown.wait()
    print("server: shutting down gracefully...")
    await asyncio.sleep(0.3)  # simulate cleanup
    print("server: done")


async def main() -> None:
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    shutdown: asyncio.Event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown.set)

    try:
        await run_server(shutdown)
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python graceful_shutdown.py
server: running (send SIGINT or SIGTERM to stop)
^C
server: shutting down gracefully...
server: done
```

Why use an `Event` instead of cancelling a task directly? `Event.set()` is
simple, synchronous, and idempotent. Your main code decides *how* to shut
down in a structured way, at a point where you have full context.

A few notes:

- **`remove_signal_handler(sig)`** unregisters the handler and returns `True`
  if one was removed, `False` otherwise. Cleaning up in `finally` is good
  practice, though `asyncio.run()` will close the loop regardless.

- **Unix only.** `add_signal_handler()` raises `NotImplementedError` on
  Windows. For portable signal handling, combine `signal.signal()` with
  `call_soon_threadsafe()` -- but most long-running async services run on
  Linux anyway.

- **Limited signal set.** You cannot handle `SIGKILL` or `SIGSTOP` (the OS
  forbids it). Common choices are `SIGINT`, `SIGTERM`, and occasionally
  `SIGHUP` for configuration reload.

!!! tip

    If your program is a simple script rather than a long-running server,
    you probably do not need signal handlers. `asyncio.run()` already
    handles `KeyboardInterrupt` (from `SIGINT`) by cancelling the main
    task and running the shutdown sequence. Signal handlers are for
    *custom* shutdown behavior -- draining connections, writing state to
    disk, logging a clean exit.

## Summary

These APIs bridge the gap between the async event loop and everything else:

| API | Direction | Use case |
| :-- | :-- | :-- |
| `future.add_done_callback()` | async → async | React to task/future completion without `await` |
| `loop.call_soon_threadsafe()` | thread → loop | Schedule a plain callback from a non-async thread |
| `asyncio.run_coroutine_threadsafe()` | thread → loop | Run a coroutine from a non-async thread, get a blocking future |
| `loop.add_signal_handler()` | OS → loop | Respond to Unix signals inside the event loop |

For the common case -- calling blocking code *from* async -- stick with
[`asyncio.to_thread()`](../beyond-the-basics/blocking-code.md). The tools
in this section are for the reverse: when synchronous code, external threads,
or the OS need to reach into your event loop. You will not need them in most
application code, but when you are building a framework, integrating with
legacy systems, or writing a server with graceful shutdown, they are essential.

---
