---
title: Beyond the Basics
description: >-
  Application-level asyncio patterns beyond the core toolkit -- offloading
  blocking work, context managers and lifetimes, stream-based networking,
  subprocesses, less-common coordination tools, shielding critical work from
  cancellation, and the Runner API.
icon: lucide/workflow
---

# Beyond the Basics

This chapter covers patterns you will reach for once you are comfortable with
[The Basics](../the-basics/index.md). Everything here is still
application-level code -- no event loop internals, no framework plumbing. These
are the recipes and tools that fill the gap between "I can write a
[`TaskGroup`](../the-basics/concurrent-tasks.md#asynciotaskgroup)" and "I can
build a production async service."

If a pattern here feels slippery, bounce back to [Concurrent
Tasks](../the-basics/concurrent-tasks.md), [Cancellation and
Timeouts](../the-basics/cancellation-and-timeouts.md), and [Resource
Management](../the-basics/resource-management.md). When you want the machinery
underneath, continue to [How Asyncio Works](../how-asyncio-works/index.md),
especially [Tasks and Futures](../how-asyncio-works/tasks-and-futures.md).

## Sections

1. [Offloading Blocking Work](offloading-blocking-work.md) --
   [`asyncio.to_thread()`](offloading-blocking-work.md#asyncioto_thread),
   [CPU-bound work with
   `ProcessPoolExecutor`](offloading-blocking-work.md#processpoolexecutor-for-cpu-bound-work),
   and [choosing the right offloading
   tool](offloading-blocking-work.md#when-to-use-what).

2. [Context Managers and Lifetimes](context-managers-and-lifetimes.md) --
   the [class-based
   protocol](context-managers-and-lifetimes.md#the-class-based-protocol),
   [`@asynccontextmanager`](context-managers-and-lifetimes.md#asynccontextmanager)
   helpers, [`AsyncExitStack`](context-managers-and-lifetimes.md#asyncexitstack),
   and [composing lifetimes](context-managers-and-lifetimes.md#composing-lifetimes).

3. [Streams](streams.md) --
   [opening a client connection](streams.md#opening-a-client-connection),
   [stream resource management](streams.md#resource-management-for-streams),
   [building a TCP server](streams.md#building-a-tcp-server), and [timeouts on
   stream operations](streams.md#timeouts-on-stream-operations). This is a
   reference companion section.

4. [Subprocesses](subprocesses.md) -- [exec vs
   shell](subprocesses.md#exec-vs-shell), [the `communicate()`
   pattern](subprocesses.md#the-default-pattern-communicate), and [pipe
   deadlocks](subprocesses.md#the-main-pitfall-pipe-deadlocks). This is a
   reference companion section.

5. [Advanced Coordination](advanced-coordination.md) --
   [`Lock`](advanced-coordination.md#asynciolock),
   [`Condition`](advanced-coordination.md#asynciocondition),
   [`Barrier`](advanced-coordination.md#asynciobarrier),
   [`BoundedSemaphore`](advanced-coordination.md#asyncioboundedsemaphore), and
   [`PriorityQueue`/`LifoQueue`](advanced-coordination.md#asynciopriorityqueue-and-asynciolifoqueue).
   This is a reference companion section.

6. [Shielding](shielding.md) -- [the recommended shielding
   pattern](shielding.md#the-recommended-pattern), [structured cleanup
   without shielding](shielding.md#structured-cleanup-without-shielding),
   and [when to use shielding](shielding.md#when-to-use-shielding).

7. [Runner](runner.md) -- [when to use `Runner`](runner.md#when-to-use-runner),
   [the shape of the API](runner.md#the-shape-of-the-api), and
   [cleanup](runner.md#cleanup). This is a reference companion section.
