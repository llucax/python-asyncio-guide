---
title: How Asyncio Works
description: >-
  Understand the machinery underneath asyncio — the event loop, tasks and
  futures, cancellation internals, and the shutdown sequence. Essential
  knowledge for diagnosing surprising behavior in async programs.
icon: lucide/book-open
---

# How Asyncio Works

Chapters 1 and 2 taught you how to *use* asyncio. This chapter teaches you how
it *works*. You don't need this material to write correct async programs -- but
you do need it when something surprising happens and you want to understand
exactly why.

Everything here is about the machinery underneath: the event loop, the
relationship between tasks and futures, how cancellation is actually
implemented, and what [`asyncio.run()`][asyncio-run] does during shutdown. This is also where
the guide introduces the "unsafe" APIs -- [`create_task()`][create-task], [`task.cancel()`][task-cancel],
[`call_soon()`][call-soon] -- not as tools to use day-to-day, but as the building blocks
that the safe abstractions from Chapters 1 and 2 are built on.

## Sections

1. [The Event Loop](the-event-loop.md) — the single-threaded scheduler at the
   heart of asyncio. Ready queues, I/O polling, timers, [`call_soon()`][call-soon],
   `#!py call_later()`, `#!py call_at()`.

2. [Tasks and Futures](tasks-and-futures.md) — [`asyncio.Future`][asyncio-future], [`asyncio.Task`][asyncio-task],
   [`create_task()`][create-task], the task lifecycle, and how tasks drive coroutines forward.

3. [Cancellation Internals](cancellation-internals.md) — [`task.cancel()`][task-cancel],
   [`task.cancelling()`][task-cancelling], `#!py task.uncancel()`, and how [`asyncio.timeout()`][asyncio-timeout] and
   [`TaskGroup`][taskgroup] use them under the hood.

4. [Shutdown Sequence](shutdown-sequence.md) — what [`asyncio.run()`][asyncio-run] does when
   your main coroutine returns: pending task cancellation, async generator
   shutdown, executor shutdown, and loop closure.

[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[task-cancel]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel
[call-soon]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon
[asyncio-future]: https://docs.python.org/3/library/asyncio-future.html#asyncio.Future
[asyncio-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task
[task-cancelling]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancelling
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup