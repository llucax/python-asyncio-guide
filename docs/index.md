---
title: "Asyncio: A Concept-First Learning Guide"
description: >-
  An opinionated, concept-first guide to Python's asyncio library. Learn
  async/await through modern, structured concurrency patterns, then use
  the official docs as your API reference.
---

# Asyncio: A Concept-First Learning Guide

This is an opinionated learning guide for Python's built-in
[`asyncio`][asyncio].

The structure and teaching style are inspired by
[Trio's excellent documentation][trio-docs].
[Trio][trio-docs] deliberately designs for structured concurrency and
cancellation ergonomics, and this guide borrows that point of view when
teaching [`asyncio`][asyncio]. If you can adopt [Trio][trio-docs], it is often
a great choice. But many codebases cannot switch away from the standard
library. [`asyncio`][asyncio] is widely deployed, and this guide aims to fill
the gap in high-quality learning resources for it.

This guide complements the
[official asyncio documentation][official-asyncio-documentation]; it does not
replace it. The intended split is simple:

- **Use this guide as your primary learning path.** It is opinionated and
  focuses on the patterns this guide thinks you should prefer for modern
  Python 3.11+ application code: structured concurrency, timeout scopes,
  explicit lifetimes, cancellation-safe cleanup, backpressure, debugging,
  and realistic program structure.
- **Use the official docs as your primary reference.** They are the best place
  to look up full signatures, platform notes, version changes, exhaustive API
  details, and lower-level or historical APIs that this guide intentionally
  de-emphasizes.

That means this guide is not a neutral tour of every asyncio style. If you have
already written a fair amount of async code but mostly through older patterns
-- ad hoc task spawning, manual loop plumbing, or pre-[`TaskGroup`][taskgroup]
habits -- that is exactly the kind of experience this guide aims to help you
update.

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

This guide assumes **Python 3.11 or newer**. It uses
[`asyncio.TaskGroup`][asyncio-taskgroup], [`asyncio.timeout()`][asyncio-timeout],
and other modern APIs throughout without version guards.

## How To Read This Guide

This guide is designed to be read linearly. The early chapters teach the safe
defaults first, and the later chapters explain the machinery and escape hatches
underneath.

If you are deciding where to focus, each chapter serves a slightly different
reader:

- **[The Basics](the-basics/index.md)** is for almost everyone. Start here if
  [`async`][async]/[`await`][await] still feels slippery, if you have only used
  async through a framework, or if you already know asyncio but want to
  replace older habits with safer 3.11+ defaults.
- **[Beyond the Basics](beyond-the-basics/index.md)** is for application code
  once the core model feels solid. It covers the patterns that sit between
  "I can use a `TaskGroup`" and "I can build a production async service."
- **[How Asyncio Works](how-asyncio-works/index.md)** is for when you need the
  runtime mental model: debugging surprising behavior, understanding why the
  safe rules exist, or reading older and lower-level code without treating its
  patterns as your new default.
- **[The Low-Level Toolkit](the-low-level-toolkit/index.md)** is for library
  authors, framework authors, and infrastructure code that truly needs the
  low-level APIs. Most application code can skip it on a first pass.
- **Appendices** are for reference and revisiting: the checkpoint contract,
  consolidated best practices, and a dedicated debugging guide.

## Chapter Index

You can use this index to get a quick sense of what each chapter covers, or to
jump straight to a section. Still, the guide works best when you read it
linearly.

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
    * [Coordination](the-basics/coordination.md) -- Use queues, events, and
      semaphores for inter-task coordination.
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
      Reach for locks, conditions, barriers, bounded semaphores, and
      specialty queues when the basics are not enough.
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
