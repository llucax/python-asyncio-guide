---
title: How Asyncio Works
description: >-
  Understand the machinery underneath asyncio -- the event loop, tasks and
  futures, cancellation internals, and the shutdown sequence. Essential
  knowledge for diagnosing surprising behavior in async programs.
icon: lucide/cpu
---

# How Asyncio Works

[The Basics](../the-basics/index.md) and
[Beyond the Basics](../beyond-the-basics/index.md) taught you how to *use*
asyncio. This chapter teaches you how it *works*. You do not need this
material to write correct async programs -- but you do need it when something
surprising happens and you want to understand exactly why.

Everything here is about the machinery underneath: the event loop, the
relationship between tasks and futures, how cancellation is actually
implemented, and [the `asyncio.run()` shutdown sequence](shutdown-sequence.md#the-asynciorun-shutdown-sequence).
This is also where the guide introduces the "unsafe" APIs --
[`create_task()`](tasks-and-futures.md#asynciocreate_task),
[`task.cancel()`](cancellation-internals.md#taskcancel),
[`call_soon()`](the-event-loop.md#call_soon) -- not as tools to use day-to-day,
but as the building blocks that the safe abstractions from Chapters 1 and 2
are built on.

This chapter is the guide's clearest differentiator from the official docs. It
is where the guide intentionally goes deep instead of linking out.

If you want the application-level rules beside the internals, keep
[Concurrent Tasks](../the-basics/concurrent-tasks.md),
[Cancellation and Timeouts](../the-basics/cancellation-and-timeouts.md), and
[Offloading Blocking Work](../beyond-the-basics/offloading-blocking-work.md) open
alongside this
chapter.

## Sections

1. [The Event Loop](the-event-loop.md) -- the single-threaded scheduler at the
   heart of asyncio. [Loop iterations](the-event-loop.md#the-loop-iteration),
   [`call_soon()`](the-event-loop.md#call_soon), and
   [timers](the-event-loop.md#timers-call_later-and-call_at).

2. [Tasks and Futures](tasks-and-futures.md) --
   [`Future`](tasks-and-futures.md#asynciofuture),
   [`Task`](tasks-and-futures.md#asynciotask),
   [`create_task()`](tasks-and-futures.md#asynciocreate_task), and the
   [task lifecycle](tasks-and-futures.md#task-lifecycle).

3. [Cancellation Internals](cancellation-internals.md) --
   [`task.cancel()`](cancellation-internals.md#taskcancel),
   [the cancellation counter](cancellation-internals.md#the-cancellation-counter),
   [timeouts](cancellation-internals.md#how-asynciotimeout-works-internally),
   and
   [`TaskGroup`](cancellation-internals.md#how-taskgroup-works-internally)
   under the hood.

4. [Shutdown Sequence](shutdown-sequence.md) --
   [the `asyncio.run()` shutdown sequence](shutdown-sequence.md#the-asynciorun-shutdown-sequence),
   [async generator finalization](shutdown-sequence.md#async-generator-finalization),
   [executor shutdown](shutdown-sequence.md#executor-shutdown), and loop
   closure.
