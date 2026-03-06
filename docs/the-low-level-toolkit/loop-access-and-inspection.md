---
title: Loop Access and Inspection
description: >-
  Get the running event loop with asyncio.get_running_loop(), inspect loop
  state, enumerate live tasks, and understand when you need the loop object
  directly for scheduling callbacks or creating futures.
---

# Loop Access and Inspection

Most async code never touches the event loop directly. You `await` coroutines,
create tasks through a `TaskGroup`, and let `asyncio.run()` manage the loop's
lifecycle. But if you are writing a library, a framework, or a bridge to
non-async code, there are times you need the loop object itself -- to schedule
a callback, create a bare future, or run something in an executor. This
section covers how to get the loop, how to inspect it, and how to see what
tasks are currently alive.

## `asyncio.get_running_loop()`

[`asyncio.get_running_loop()`](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop)
is the only way you should obtain the event loop. Call it from inside a
running coroutine and it returns the loop that is currently executing. Call it
from outside -- before `asyncio.run()` starts, or from a plain thread with no
loop -- and it raises `RuntimeError`.

```python
# get_loop.py
import asyncio


async def show_loop() -> None:
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    print(f"loop type: {type(loop).__name__}")
    print(f"loop running: {loop.is_running()}")


if __name__ == "__main__":
    asyncio.run(show_loop())
```

```text
$ python get_loop.py
loop type: _UnixSelectorEventLoop
loop running: True
```

That is the entire API. There is no setter, no global variable to configure --
you ask for the running loop and you get it, or you get an exception.

### When you actually need the loop

In day-to-day application code, you rarely need the loop object. The cases
where you do are almost all low-level:

- **`loop.run_in_executor()`** -- to run blocking code in a custom
  `ProcessPoolExecutor` (for a plain `ThreadPoolExecutor`,
  [`asyncio.to_thread()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread)
  is simpler).
- **`loop.create_future()`** -- to create a bare
  [`Future`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future)
  for manual result resolution in protocol or callback-style code.
- **`loop.call_soon()` / `loop.call_later()` / `loop.call_at()`** -- to
  schedule plain callbacks instead of coroutines.
- **`loop.call_soon_threadsafe()`** -- to push work onto the event loop from
  another thread.

If none of these apply, you do not need the loop.

## Loop Inspection

The loop object has two boolean queries that are useful for defensive
programming in library code:

- **`loop.is_running()`** -- returns `True` if the loop is currently executing
  callbacks. Inside a coroutine this is always `True`; it is mainly useful in
  library teardown code that might run after `asyncio.run()` returns.
- **`loop.is_closed()`** -- returns `True` after someone has called
  `loop.close()`. A closed loop cannot be restarted. Calling any scheduling
  method on a closed loop raises `RuntimeError`.

A practical use case: a library that holds a reference to the loop (for
example, to schedule cleanup from a `__del__` method or a finalizer) should
check both before touching it:

```python
# defensive_cleanup.py
import asyncio


class ConnectionPool:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _schedule_cleanup(self) -> None:
        if self._loop.is_running() and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._do_cleanup)

    def _do_cleanup(self) -> None:
        print("cleaning up pool resources")
```

!!! note

    Checking `is_running()` and `is_closed()` avoids `RuntimeError`
    exceptions that would otherwise fire silently during interpreter
    shutdown, when the loop has already been torn down.

## Task Introspection

Two module-level functions let you see what tasks exist at any point in time:

- [`asyncio.current_task()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.current_task)
  -- returns the `Task` that is currently executing, or `None` if called from
  a callback or from outside a task.
- [`asyncio.all_tasks()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.all_tasks)
  -- returns a `set` of all tasks that are not yet done on the running loop.
  The set includes the current task.

Both accept an optional `loop` argument, but you should almost never pass it
-- when omitted they use the running loop automatically.

Here is a small monitoring example that lists every live task:

```python
# task_introspection.py
import asyncio


async def worker(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return f"{name} done"


async def monitor() -> None:
    """Print all live tasks, then finish."""
    current: asyncio.Task[None] | None = asyncio.current_task()
    all_live: set[asyncio.Task[object]] = asyncio.all_tasks()

    print(f"current task: {current.get_name() if current else None}")
    print(f"total live tasks: {len(all_live)}")
    for t in sorted(all_live, key=lambda t: t.get_name()):
        print(f"  {t.get_name():>12}  done={t.done()}")


async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(worker("alpha", 1.0), name="alpha")
        tg.create_task(worker("bravo", 2.0), name="bravo")
        tg.create_task(monitor(), name="monitor")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python task_introspection.py
current task: monitor
total live tasks: 4
         Task-1  done=False
          alpha  done=False
          bravo  done=False
        monitor  done=False
```

Four tasks: the three you created plus the implicit `Task-1` that wraps
`main()` itself. This kind of snapshot is invaluable for debugging hung
programs or building health-check endpoints that report what your async
application is doing.

!!! tip

    `asyncio.all_tasks()` is what `asyncio.run()` calls during
    [shutdown](../how-asyncio-works/shutdown-sequence.md) to find and cancel
    leftover tasks. If you ever need to implement a similar
    graceful-shutdown routine yourself, this is the function to reach for.

## What You Don't Need

If you have seen older asyncio code or tutorials, you may have encountered
these functions:

- `asyncio.get_event_loop()`
- `asyncio.set_event_loop()`
- `asyncio.set_event_loop_policy()` / custom event loop policies

Forget they exist. They date from a time before `asyncio.run()`, when you
had to create and manage the loop manually. In modern Python (3.10+),
`get_event_loop()` emits a `DeprecationWarning` when no loop is running, and
the entire policy system is a relic of an era when swapping event loop
implementations (uvloop, Proactor on Windows) required global mutation at
startup. Today, `asyncio.run()` accepts a `loop_factory` parameter if you
need a custom loop:

```python
import asyncio
import uvloop

asyncio.run(main(), loop_factory=uvloop.new_event_loop)
```

That single keyword argument replaces the entire policy machinery. Inside
your running program, `get_running_loop()` is the only accessor you need.

---
