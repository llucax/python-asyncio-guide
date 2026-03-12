---
title: Futures
description: >-
  A concise guide to bare asyncio futures. Learn when you need them, how to
  bridge callback-style code into async/await, and when the official docs are
  the right place for the full reference.
---

# Futures

Application code rarely needs bare futures. That is why this section is short.

When you do need them, it is usually because you are building glue code between
two worlds:

- callback-driven code on one side
- `await`-driven code on the other

## The Three Operations That Matter Most

The practical future workflow is usually just this:

1. create one with [`loop.create_future()`][create-future]
2. resolve it later with [`set_result()`][set-result] or [`set_exception()`][set-exception]
3. `await` it from async code

## Canonical Pattern: Bridge a Callback API

```python title="callback_bridge.py"
import asyncio
from typing import Callable


def start_operation(callback: Callable[[str], None]) -> None:
    loop = asyncio.get_running_loop()
    loop.call_later(0.2, callback, "done")


async def start_operation_async() -> str:
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def on_done(value: str) -> None:
        if not future.done():
            future.set_result(value)

    start_operation(on_done)
    return await future
```

That is the core use case. The future becomes a one-shot handoff point between
"someone calls me back later" and "I want to await a result now".

## `#!py wrap_future()`

If another subsystem hands you a [`concurrent.futures.Future`][concurrent-future],
use [`asyncio.wrap_future()`][wrap-future] so you can await it from asyncio.

If *you* control the submission, prefer [`asyncio.to_thread()`][to-thread] or
[`loop.run_in_executor()`][run-in-executor] instead. Those are usually cleaner.

## When Not to Reach for a Bare Future

Do not use a future when one of these higher-level tools already fits:

- [`TaskGroup`][taskgroup] for concurrent child tasks
- [`Queue`][queue] for producer/consumer handoff
- streams for network I/O
- [`asyncio.to_thread()`][to-thread] for blocking sync functions

If you are not bridging callback-style code, a bare future is often a sign that
you are working one layer too low.

## What to Read Next

- Full reference: [Futures][futures]
- The conceptual model behind futures and tasks:
  [Tasks and Futures](../how-asyncio-works/tasks-and-futures.md)

[create-future]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_future
[wrap-future]: https://docs.python.org/3/library/asyncio-future.html#asyncio.wrap_future
[concurrent-future]: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future
[to-thread]: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
[run-in-executor]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[futures]: https://docs.python.org/3/library/asyncio-future.html
[set-result]: https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_result
[set-exception]: https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_exception