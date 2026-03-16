---
title: "Asyncio: A Concept-First Learning Guide"
description: >-
  An opinionated, concept-first guide to Python's asyncio library. Learn
  async/await through modern, structured concurrency patterns, then use the
  official docs as your API reference.
icon: lucide/house
---

# Asyncio: A Concept-First Learning Guide

This is an opinionated learning guide for Python's built-in
[`asyncio`][asyncio].

The structure and teaching style are inspired by [Trio's excellent
documentation][trio-docs]. [Trio][trio-docs] deliberately designs for
structured concurrency and cancellation ergonomics, and this guide borrows that
point of view when teaching [`asyncio`][asyncio]. If you can adopt
[Trio][trio-docs], it is often a great choice. But many codebases cannot switch
away from the standard library. [`asyncio`][asyncio] is widely deployed, and
this guide aims to fill the gap in high-quality learning resources for it.

This guide complements the [official asyncio
documentation][official-asyncio-documentation]; it does not replace it. The
intended split is simple:

- **Use this guide as your primary learning path.** It is opinionated and
  focuses on the patterns this guide thinks you should prefer for modern Python
  3.11+ application code: structured concurrency, checkpoints, timeout scopes,
  explicit lifetimes, cancellation-safe cleanup, backpressure, debugging, and
  realistic program structure.
- **Use the official docs as your primary reference.** They are the best place
  to look up full signatures, platform notes, version changes, exhaustive API
  details, and lower-level or historical APIs that this guide intentionally
  de-emphasizes.

That means this guide is not a neutral tour of every asyncio style. If you have
already written a fair amount of async code but mostly through older patterns
-- ad hoc task spawning, manual loop plumbing, or pre-`TaskGroup` habits --
that is exactly the kind of experience this guide aims to help you update.

Some sections in this guide are deliberately short and point you at the
official docs when the stdlib reference is already strong. That is by design.
The goal is to keep this guide cohesive and complete without turning it into a
second API manual.

## Prerequisites

You should be comfortable writing and calling Python functions, handling
exceptions, and reading tracebacks. A rough idea of what I/O means (network
requests, reading files) is helpful. You do **not** need prior experience with
threads or event loops -- we build up the mental model from scratch.

### Python Version

This guide assumes **Python 3.11 or newer**. It uses `TaskGroup`,
`asyncio.timeout()`, and other modern APIs throughout without version guards.

## How To Read This Guide

This guide is designed to be read linearly. The early chapters teach the safe
defaults first, and the later chapters explain the machinery and escape hatches
underneath.

If you are deciding where to focus, each chapter serves a slightly different
reader:

- **[The Basics](the-basics/index.md)** is for virtually everyone. Read it even
  if you already ship asyncio code, because it introduces the guide's core
      mental models -- especially checkpoints, cooperative cancellation, and
      task ownership -- and rebuilds day-to-day patterns around safer 3.11+
      defaults. The official docs cover the mechanics, but this guide makes the
      relationship between checkpoints, cancellation delivery, and cleanup
      rules, all key to correct async code, more explicit and central.
- **[Beyond the Basics](beyond-the-basics/index.md)** is for application code
  once the core model feels solid. It covers the patterns that sit between "I
  can use a `TaskGroup`" and "I can build a production async service."
- **[How Asyncio Works](how-asyncio-works/index.md)** is for when you need the
  runtime mental model: debugging surprising behavior, understanding why the
  safe rules exist, or reading older and lower-level code without treating its
  patterns as your new default.
- **[The Low-Level Toolkit](the-low-level-toolkit/index.md)** is for library
  authors, framework authors, and infrastructure code that truly needs the
  low-level APIs. Most application code can skip it on a first pass.
- **[Appendices](appendices/index.md)** are for reference and revisiting: the
  [checkpoint contract](appendices/checkpoint-contract.md#implications),
  consolidated [best practices](appendices/best-practices.md), and a dedicated
  [debugging guide](appendices/debugging.md#diagnosing-a-blocked-loop).

## Chapter Index

You can use this index to get a quick sense of what each chapter covers, or to
jump straight to a section. Still, the guide works best when you read it
linearly.

1. [The Basics](the-basics/index.md) -- Start here. Learn the core vocabulary,
   [checkpoints](the-basics/getting-started.md#checkpoints),
   [cancellation](the-basics/cancellation-and-timeouts.md#cancellation), and
   [`TaskGroup`](the-basics/concurrent-tasks.md#asynciotaskgroup)-based
   patterns for day-to-day async programming.

     * [Getting Started](the-basics/getting-started.md) -- Learn
       [`await`](the-basics/getting-started.md#await), [the async
       sandwich](the-basics/getting-started.md#the-async-sandwich),
       [`asyncio.sleep()`](the-basics/getting-started.md#asynciosleep), and
       [checkpoints](the-basics/getting-started.md#checkpoints).
     * [Concurrent Tasks](the-basics/concurrent-tasks.md) -- Use
       [`TaskGroup`](the-basics/concurrent-tasks.md#asynciotaskgroup),
       [structured
       concurrency](the-basics/concurrent-tasks.md#structured-concurrency), and
       [`ExceptionGroup` and
       `except*`](the-basics/concurrent-tasks.md#exceptiongroup-and-except) for
       child-task failures.
     * [Cancellation and Timeouts](the-basics/cancellation-and-timeouts.md) --
       Understand
       [cancellation](the-basics/cancellation-and-timeouts.md#cancellation),
       [timeouts](the-basics/cancellation-and-timeouts.md#timeouts), and
       [sibling
       cancellation](the-basics/concurrent-tasks.md#sibling-cancellation).
     * [Resource Management](the-basics/resource-management.md) -- Clean up
       with [`async
       with`](the-basics/resource-management.md#async-context-managers-and-async-with),
       [async generators](the-basics/resource-management.md#async-generators),
       and
       [`contextlib.aclosing()`](the-basics/resource-management.md#contextlibaclosing).
      * [Coordination](the-basics/coordination.md) -- Use
        [`asyncio.Queue`](the-basics/coordination.md#asyncioqueue),
        [`asyncio.Event`](the-basics/coordination.md#asyncioevent), and
        [`asyncio.Semaphore`](the-basics/coordination.md#asynciosemaphore) for
        inter-task coordination.
     * [Building a Pipeline](the-basics/building-a-pipeline.md) -- Combine
       [bounded
       queues](the-basics/building-a-pipeline.md#step-2-backpressure-with-bounded-queues),
       [error
       handling](the-basics/building-a-pipeline.md#step-3-error-handling), and
       [clean
       shutdown](the-basics/building-a-pipeline.md#step-4-full-pipeline-with-clean-shutdown)
       into a realistic pipeline.
     * [Debugging](the-basics/debugging.md) -- Catch [forgotten
       `await`s](the-basics/debugging.md#forgotten-await), [blocking
       calls](the-basics/debugging.md#blocking-call-in-async-code), and
       [cancellation bugs](the-basics/debugging.md#swallowing-cancellederror)
       early.

2. [Beyond the Basics](beyond-the-basics/index.md) -- Learn the advanced
   application-level patterns for [stream-based
   networking](beyond-the-basics/streams.md#opening-a-client-connection),
   [blocking-code offloading](beyond-the-basics/blocking-code.md#asyncioto_thread),
   [shielding](beyond-the-basics/shielding.md#when-to-use-shielding), and
   other production-oriented asyncio work.

     * [Blocking Code](beyond-the-basics/blocking-code.md) -- Decide when to
       use
       [`asyncio.to_thread()`](beyond-the-basics/blocking-code.md#asyncioto_thread),
       [process pools](beyond-the-basics/blocking-code.md#processpoolexecutor),
       and each offloading strategy.
     * [Shielding](beyond-the-basics/shielding.md) -- Use [safe shielding
       patterns](beyond-the-basics/shielding.md#safe-patterns) for truly
       critical work without creating orphaned tasks.
     * [Custom Context Managers](beyond-the-basics/custom-context-managers.md)
       -- Build reusable async setup and teardown blocks with
       [`@asynccontextmanager`](beyond-the-basics/custom-context-managers.md#asynccontextmanager)
       and
       [`AsyncExitStack`](beyond-the-basics/custom-context-managers.md#asyncexitstack).
      * [Advanced Coordination](beyond-the-basics/advanced-coordination.md) --
        Reach for
        [`Lock`](beyond-the-basics/advanced-coordination.md#asynciolock),
        [`Condition`](beyond-the-basics/advanced-coordination.md#asynciocondition),
        [`Barrier`](beyond-the-basics/advanced-coordination.md#asynciobarrier),
        and
        [`PriorityQueue`/`LifoQueue`](beyond-the-basics/advanced-coordination.md#priorityqueue-and-lifoqueue)
        when the basics are not enough.
      * [Streams](beyond-the-basics/streams.md) -- Work with [client
        connections](beyond-the-basics/streams.md#opening-a-client-connection),
        [TCP servers](beyond-the-basics/streams.md#building-a-tcp-server), and
        [stream cleanup](beyond-the-basics/streams.md#resource-management-for-streams).
      * [Subprocesses](beyond-the-basics/subprocesses.md) -- Use [the
        `communicate()`
        pattern](beyond-the-basics/subprocesses.md#the-default-pattern-communicate)
        and avoid [pipe
       deadlocks](beyond-the-basics/subprocesses.md#the-main-pitfall-pipe-deadlocks).
     * [Runner](beyond-the-basics/runner.md) -- Learn [when to use
       `Runner`](beyond-the-basics/runner.md#when-to-use-runner) when you need
       multiple top-level coroutines in one process.

3. [How Asyncio Works](how-asyncio-works/index.md) -- Learn the runtime
   machinery underneath [the event
   loop](how-asyncio-works/the-event-loop.md#the-loop-iteration), [tasks and
   futures](how-asyncio-works/tasks-and-futures.md#asynciofuture), and
   [cancellation
   delivery](how-asyncio-works/cancellation-internals.md#taskcancel).

     * [The Event Loop](how-asyncio-works/the-event-loop.md) -- See how [loop
       iterations](how-asyncio-works/the-event-loop.md#the-loop-iteration),
       [`call_soon()`](how-asyncio-works/the-event-loop.md#call_soon), and
       [timers](how-asyncio-works/the-event-loop.md#timers-call_later-and-call_at)
       drive execution.
     * [Tasks and Futures](how-asyncio-works/tasks-and-futures.md) --
       Understand how
       [`Future`](how-asyncio-works/tasks-and-futures.md#asynciofuture),
       [`Task`](how-asyncio-works/tasks-and-futures.md#asynciotask), and
       [`create_task()`](how-asyncio-works/tasks-and-futures.md#asynciocreate_task)
       drive coroutines forward.
     * [Cancellation Internals](how-asyncio-works/cancellation-internals.md) --
       Learn how
       [`task.cancel()`](how-asyncio-works/cancellation-internals.md#taskcancel),
       [the cancellation
       counter](how-asyncio-works/cancellation-internals.md#the-cancellation-counter),
       and internal timeout machinery work under the hood.
     * [Shutdown Sequence](how-asyncio-works/shutdown-sequence.md) -- Follow
       [the `asyncio.run()` shutdown
       sequence](how-asyncio-works/shutdown-sequence.md#the-asynciorun-shutdown-sequence)
       when the main coroutine finishes.

4. [The Low-Level Toolkit](the-low-level-toolkit/index.md) -- Learn the
   low-level building blocks for [loop
   access](the-low-level-toolkit/loop-access-and-inspection.md#when-you-actually-need-the-loop),
   [manual task
   coordination](the-low-level-toolkit/task-coordination.md#which-tool-fits-which-job),
   and [cross-thread
   scheduling](the-low-level-toolkit/callbacks-and-threading.md#call_soon_threadsafe).

     * [Loop Access and
       Inspection](the-low-level-toolkit/loop-access-and-inspection.md) -- Know
       [when you really need the
       loop](the-low-level-toolkit/loop-access-and-inspection.md#when-you-actually-need-the-loop)
       and which inspection hooks matter.
     * [Task Coordination](the-low-level-toolkit/task-coordination.md) -- Use
       [`asyncio.wait()`](the-low-level-toolkit/task-coordination.md#asynciowait),
       [`asyncio.as_completed()`](the-low-level-toolkit/task-coordination.md#asyncioas_completed),
       and
       [`asyncio.wait_for()`](the-low-level-toolkit/task-coordination.md#asynciowait_for).
     * [Futures](the-low-level-toolkit/futures.md) -- Work with [callback
       bridging](the-low-level-toolkit/futures.md#canonical-pattern-bridge-a-callback-api)
       and [`wrap_future()`](the-low-level-toolkit/futures.md#wrap_future).
     * [Callbacks and
       Threading](the-low-level-toolkit/callbacks-and-threading.md) -- Use
       [`call_soon_threadsafe()`](the-low-level-toolkit/callbacks-and-threading.md#call_soon_threadsafe)
       and
       [`run_coroutine_threadsafe()`](the-low-level-toolkit/callbacks-and-threading.md#run_coroutine_threadsafe)
       from synchronous code.
     * [Transports and
       Protocols](the-low-level-toolkit/transports-and-protocols.md) --
       Understand [the callback-based networking
       model](the-low-level-toolkit/transports-and-protocols.md#the-model-in-one-sentence)
       underneath streams.

5. [Appendices](appendices/index.md) -- Reference material for
   [checkpoint behavior](appendices/checkpoint-contract.md#always-suspends),
   [best practices](appendices/best-practices.md), and [debugging
   workflows](appendices/debugging.md#useful-diagnostic-patterns).

     * [Checkpoint Contract](appendices/checkpoint-contract.md) -- guide-level
       reference for which common operations
       [always suspend](appendices/checkpoint-contract.md#always-suspends),
       [conditionally suspend](appendices/checkpoint-contract.md#conditionally-suspends),
       or [never suspend](appendices/checkpoint-contract.md#never-suspends).

     * [Best Practices, Pitfalls, and Gotchas](appendices/best-practices.md) --
       consolidated best practices, pitfalls, and gotchas you can skim before
       a review.

     * [Debugging Guide](appendices/debugging.md) -- practical techniques for
       [blocked loops](appendices/debugging.md#diagnosing-a-blocked-loop),
       [task leaks](appendices/debugging.md#diagnosing-task-leaks),
       [timeout failures](appendices/debugging.md#diagnosing-a-cancelled-timeout),
       and more.

[asyncio]: https://docs.python.org/3/library/asyncio.html
[official-asyncio-documentation]: https://docs.python.org/3/library/asyncio.html
[trio-docs]: https://trio.readthedocs.io/en/stable/
