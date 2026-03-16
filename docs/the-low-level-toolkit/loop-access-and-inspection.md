---
title: Loop Access and Inspection
description: >-
  A concise guide to getting the running loop, inspecting live tasks, and
  deciding when you really need the loop object instead of staying at the
  high-level asyncio layer.
---

# Loop Access and Inspection

Most async code never touches the loop directly. That is a feature, not a
limitation.

This section is intentionally short because the official event-loop docs are
already good. Use this section to answer two questions:

1. When do you actually need the loop object?
2. Which inspection hooks are worth remembering?

## The Normal Accessor: `#!py get_running_loop()`

Inside a running coroutine, use [`asyncio.get_running_loop()`][get-running-loop].

```python
async def show_loop() -> None:
    loop = asyncio.get_running_loop()
    print(type(loop).__name__)
```

That is the modern accessor to remember.

If you are inside application code and you feel tempted to reach for
[`get_event_loop()`][get-event-loop], stop and reconsider. Most of the time you either want
[`get_running_loop()`][get-running-loop] or no loop access at all.

## When You Actually Need the Loop

In practice, you usually need the loop for one of four reasons:

- creating a bare future with [`loop.create_future()`][create-future]
- scheduling a plain callback with [`loop.call_soon()`][call-soon]
- jumping from another thread into the loop with
  [`loop.call_soon_threadsafe()`][call-soon-threadsafe]
- running blocking work in a custom executor with
  [`loop.run_in_executor()`][run-in-executor]

If none of those apply, stay at the higher-level API.

## Task Inspection You Should Remember

Two module-level helpers are worth keeping in your head:

- [`asyncio.current_task()`][current-task]
- [`asyncio.all_tasks()`][all-tasks]

They are useful for diagnostics, leak hunting, and graceful-shutdown code.

```python
import asyncio


async def monitor() -> None:
    current = asyncio.current_task()
    live = asyncio.all_tasks()

    print(f"current: {current.get_name() if current else None}")
    for task in sorted(live, key=lambda t: t.get_name()):
        print(task.get_name(), task.done())
```

If you are debugging a hung program and want a snapshot of "what is still
alive?", `#!py all_tasks()` is the first tool to try.

## What This Page Deliberately Does Not Cover

This guide does not try to be a second event-loop reference. For the full list
of loop methods, event-loop implementations, callback handles, timers, socket
helpers, and platform notes, go straight to the official docs.

## What to Read Next

- Full event-loop reference: [Event Loop][event-loop]
- Why these low-level APIs exist at all:
  [The Event Loop](../how-asyncio-works/the-event-loop.md)
- Bare futures in practice: [Futures](futures.md)

[get-running-loop]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop
[create-future]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_future
[call-soon]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon
[call-soon-threadsafe]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon_threadsafe
[run-in-executor]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor
[current-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.current_task
[all-tasks]: https://docs.python.org/3/library/asyncio-task.html#asyncio.all_tasks
[event-loop]: https://docs.python.org/3/library/asyncio-eventloop.html
[get-event-loop]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_event_loop