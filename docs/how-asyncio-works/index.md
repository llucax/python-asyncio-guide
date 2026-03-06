# How Asyncio Works

Previous: [Beyond the Basics](../02-beyond-the-basics/index.md)
Next: [The Low-Level Toolkit](../04-the-low-level-toolkit/index.md)

Chapters 1 and 2 taught you how to *use* asyncio. This chapter teaches you how
it *works*. You don't need this material to write correct async programs -- but
you do need it when something surprising happens and you want to understand
exactly why.

Everything here is about the machinery underneath: the event loop, the
relationship between tasks and futures, how cancellation is actually
implemented, and what `asyncio.run()` does during shutdown. This is also where
the guide introduces the "unsafe" APIs -- `create_task()`, `task.cancel()`,
`call_soon()` -- not as tools to use day-to-day, but as the building blocks
that the safe abstractions from Chapters 1 and 2 are built on.

## Sections

1. [The Event Loop](the-event-loop.md) — the single-threaded scheduler at the
   heart of asyncio. Ready queues, I/O polling, timers, `call_soon()`,
   `call_later()`, `call_at()`.

2. [Tasks and Futures](tasks-and-futures.md) — `asyncio.Future`, `asyncio.Task`,
   `create_task()`, the task lifecycle, and how tasks drive coroutines forward.

3. [Cancellation Internals](cancellation-internals.md) — `task.cancel()`,
   `task.cancelling()`, `task.uncancel()`, and how `asyncio.timeout()` and
   `TaskGroup` use them under the hood.

4. [Shutdown Sequence](shutdown-sequence.md) — what `asyncio.run()` does when
   your main coroutine returns: pending task cancellation, async generator
   shutdown, executor shutdown, and loop closure.
