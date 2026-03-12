---
title: "Asyncio: A Concept-First Learning Guide"
description: >-
  A structured, concept-first guide to Python's asyncio library. Learn
  async/await from the ground up with modern, structured concurrency
  patterns, and use the official docs as your API reference.
---

# Asyncio: A Concept-First Learning Guide

This is a general-purpose learning guide for Python's built-in
[`asyncio`][asyncio].

The structure and teaching style are inspired by
[Trio's excellent documentation][trio-docs].
[Trio][trio-docs] deliberately designs for structured concurrency and
cancellation ergonomics. If you can adopt [Trio][trio-docs], it is often a
great choice. But many codebases cannot switch away from the standard library.
[`asyncio`][asyncio] is widely deployed, and this guide aims to fill the gap in
high-quality learning resources for it.

This guide complements the
[official asyncio documentation][official-asyncio-documentation]; it does not
replace it. The intended split is simple:

- **Use this guide as your primary learning path.** It focuses on mental
  models, structured concurrency, cancellation, cleanup, backpressure,
  debugging, and realistic program structure.
- **Use the official docs as your primary reference.** They are the best place
  to look up full signatures, platform notes, version changes, and exhaustive
  API details.

Some sections in this guide are deliberately short and point you at the official
docs when the stdlib reference is already strong. That is by design. The goal
is to keep this guide cohesive and complete without turning it into a second
API manual.

## Who This Is For

- You know Python, but [`async`][async]/[`await`][await] still feels slippery.
- You've written small [`asyncio`][asyncio] snippets, or just simple async
  functions filling the gaps when using a framework (like a web framework),
  and now need full, robust, maintainable async programs.
- You want modern, structured patterns ([`TaskGroup`][taskgroup], timeouts,
  explicit lifetimes).

## Prerequisites

You should be comfortable writing and calling Python functions, handling
exceptions, and reading tracebacks. A rough idea of what I/O means (network
requests, reading files) is helpful. You do **not** need prior experience with
threads or event loops -- we build up the mental model from scratch.

### Python Version

This guide assumes **Python 3.11 or newer**. It uses
[`asyncio.TaskGroup`][asyncio-taskgroup], [`asyncio.timeout()`][asyncio-timeout],
and other modern APIs throughout without version guards.

## How To Read This Guide

**[The Basics](the-basics/index.md)** covers all you need to write simple but
robust and correct asyncio programs.

**[Beyond the Basics](beyond-the-basics/index.md)** adds more advanced patterns
and tools that are necessary only when writing more complex programs, but are
good to know about, as knowing the right tools can make your *asyncio life*
much easier.

**[How Asyncio Works](how-asyncio-works/index.md)** explains the machinery
underneath. Not strictly necessary for day-to-day programming, but useful for
understanding why things work the way they do, and for debugging and library
work.

**[The Low-Level Toolkit](the-low-level-toolkit/index.md)** is for library and
framework authors who need to build on top of asyncio's low-level APIs.

**Appendices** are reference material: the checkpoint contract reference,
consolidated best practices, and a debugging guide.

## Chapter Index

You can use this index have a quick look into what chapter offers in more
detail, or to quickly jump to the section you need, but bear in mind that the
guide is designed to be read linearly.

1. [The Basics](the-basics/index.md) -- Learn the core vocabulary, safety
   rules, and high-level patterns for day-to-day async programming.

    * [Getting Started](the-basics/getting-started.md) -- Learn `async`/
      `await`, the async sandwich, and checkpoints.
    * [Concurrent Tasks](the-basics/concurrent-tasks.md) -- Use `TaskGroup`,
      structured concurrency, and `except*` for child-task failures.
    * [Cancellation and Timeouts](the-basics/cancellation-and-timeouts.md) --
      Understand `CancelledError`, timeout scopes, and sibling cancellation.
    * [Resource Management](the-basics/resource-management.md) -- Clean up
      locks, streams, and async generators safely under cancellation.
    * [Streams](the-basics/streams.md) -- Work with client and server streams,
      backpressure, and stream shutdown.
    * [Coordination](the-basics/coordination.md) -- Use queues, locks, events,
      and semaphores for inter-task coordination.
    * [Building a Pipeline](the-basics/building-a-pipeline.md) -- Combine
      queues, task groups, and sentinels into a realistic pipeline.
    * [Debugging](the-basics/debugging.md) -- Catch forgotten awaits, blocking
      calls, and cancellation bugs early.

2. [Beyond the Basics](beyond-the-basics/index.md) -- Learn the advanced
   application-level patterns that sit between the basics and library
   internals.

    * [Blocking Code](beyond-the-basics/blocking-code.md) -- Decide when to use
      threads, executors, and process pools.
    * [Shielding](beyond-the-basics/shielding.md) -- Protect truly critical work
      without creating orphaned tasks.
    * [Custom Context Managers](beyond-the-basics/custom-context-managers.md) --
      Build reusable async setup and teardown blocks.
    * [Advanced Coordination](beyond-the-basics/advanced-coordination.md) --
      Reach for conditions, barriers, bounded semaphores, and specialty queues
      when the basics are not enough.
    * [Subprocesses](beyond-the-basics/subprocesses.md) -- Run subprocesses
      safely and avoid pipe deadlocks.
    * [Runner](beyond-the-basics/runner.md) -- Use `asyncio.Runner` when you
      need multiple top-level coroutines in one process.

3. [How Asyncio Works](how-asyncio-works/index.md) -- Learn the runtime
   machinery underneath the high-level APIs.

    * [The Event Loop](how-asyncio-works/the-event-loop.md) -- See how ready
      queues, timers, and I/O polling drive execution.
    * [Tasks and Futures](how-asyncio-works/tasks-and-futures.md) -- Understand
      how tasks wrap coroutines and futures connect low-level callbacks to
      `await`.
    * [Cancellation Internals](how-asyncio-works/cancellation-internals.md) --
      Learn how cancellation requests are tracked and delivered under the hood.
    * [Shutdown Sequence](how-asyncio-works/shutdown-sequence.md) -- Follow what
      `asyncio.run()` does when the main coroutine finishes.

4. [The Low-Level Toolkit](the-low-level-toolkit/index.md) -- Learn the
   low-level building blocks for library and framework code.
    
    * [Loop Access and
      Inspection](the-low-level-toolkit/loop-access-and-inspection.md) -- Know
      when you really need the loop object and what it gives you.
    * [Task Coordination](the-low-level-toolkit/task-coordination.md) -- Use
      low-level waiting helpers like `wait()`, `as_completed()`, and
      `wait_for()`.
    * [Futures](the-low-level-toolkit/futures.md) -- Work with bare futures and
      bridge `concurrent.futures` safely.
    * [Callbacks and
      Threading](the-low-level-toolkit/callbacks-and-threading.md) -- Schedule
      callbacks across threads and submit coroutines from synchronous code.
    * [Transports and
      Protocols](the-low-level-toolkit/transports-and-protocols.md) --
      Understand the callback-based networking layer underneath streams.

5. Appendices -- Reference material for common patterns, best practices, and
    debugging.

    * [Checkpoint Contract](appendices/checkpoint-contract.md) -- guide-level
      reference for the common asyncio operations this guide uses and whether
      they always suspend, conditionally suspend, or never suspend.

    * [Best Practices, Pitfalls, and Gotchas](appendices/best-practices.md) --
      consolidated list of recurring mistakes and the correct patterns.

    * [Debugging Guide](appendices/debugging.md) -- practical techniques for
      diagnosing blocked loops, task leaks, timeout failures, and more.

[asyncio]: https://docs.python.org/3/library/asyncio.html
[official-asyncio-documentation]: https://docs.python.org/3/library/asyncio.html
[async]: https://docs.python.org/3/reference/compound_stmts.html#async-def
[await]: https://docs.python.org/3/reference/expressions.html#await
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[asyncio-taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[trio-docs]: https://trio.readthedocs.io/en/stable/
