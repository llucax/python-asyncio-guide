---
title: "Asyncio: A Concept-First Learning Guide"
description: >-
  A structured, concept-first guide to Python's asyncio library. Learn
  async/await from the ground up with modern, structured concurrency
  patterns targeting Python 3.11+.
---

# Asyncio: A Concept-First Learning Guide

This is a general-purpose learning guide for Python's built-in [`asyncio`][asyncio].

The structure and teaching style are inspired by
[Trio's excellent documentation][trio-docs].
[Trio][trio-docs] deliberately designs for structured concurrency and cancellation
ergonomics. If you can adopt [Trio][trio-docs], it is often a great choice. But many
codebases cannot switch away from the standard library. [`asyncio`][asyncio] is widely
deployed, and this guide aims to fill the gap in high-quality learning
resources for it.

This guide complements the
[official asyncio documentation][official-asyncio-documentation];
it does not replace it. When this guide mentions a concrete [`asyncio`][asyncio] API, it
links to the corresponding page in the Python docs.

## Who This Is For

- You know Python, but [`async`][async]/[`await`][await] still feels slippery.
- You've written small [`asyncio`][asyncio] snippets, or just simple async functions
  filling the gaps when using a framework (like a web framework), and now need
  full, robust, maintainable async programs.
- You want modern, structured patterns ([`TaskGroup`][taskgroup], timeouts, explicit
  lifetimes).

## Prerequisites

You should be comfortable writing and calling Python functions, handling
exceptions, and reading tracebacks. A rough idea of what I/O means (network
requests, reading files) is helpful. You do **not** need prior experience with
threads or event loops -- we build up the mental model from scratch.

### Python Version

This guide assumes **Python 3.11 or newer**. It uses [`asyncio.TaskGroup`][asyncio-taskgroup],
[`asyncio.timeout()`][asyncio-timeout], and other modern APIs throughout without version guards.

## How To Read This Guide

**Chapters 1 and 2** cover everything you need for application programming.
You can stop after Chapter 2 and write correct, maintainable async code.

**Chapter 3** explains how the machinery underneath works. Read it when you
hit a bug that surprised you and need to reason precisely about scheduling and
cancellation.

**Chapter 4** is for library and framework authors who need to build on top of
asyncio's low-level APIs.

**Appendices** are reference material: the full checkpoint contract table,
consolidated best practices, and a debugging guide.

---

## Chapters

1. [The Basics](the-basics/index.md) — [`asyncio.run()`][asyncio-run],
   coroutines, [`TaskGroup`][taskgroup], [`asyncio.timeout()`][asyncio-timeout], [`Event`][event], [`Queue`][queue], and
   everything you need for day-to-day async programming.

2. [Beyond the Basics](beyond-the-basics/index.md) — [`asyncio.to_thread()`][asyncio-to-thread],
   `#!py shield()`, subprocesses, async context managers, advanced synchronization,
   and [`asyncio.Runner`][asyncio-runner].

3. [How Asyncio Works](how-asyncio-works/index.md) — the event loop model,
   [`asyncio.Future`][asyncio-future], [`asyncio.Task`][asyncio-task], task lifecycle, and the full cancellation
   mechanics.

4. [The Low-Level Toolkit](the-low-level-toolkit/index.md) —
   `#!py get_running_loop()`, `#!py wait()`, `#!py as_completed()`, `#!py wait_for()`,
   cross-thread communication, protocols/transports, and low-level server APIs.

---

## Appendices

- [Checkpoint Contract](appendices/checkpoint-contract.md) — full table of
  which asyncio operations always suspend, conditionally suspend, or never
  suspend.

- [Best Practices, Pitfalls, and Gotchas](appendices/best-practices.md) —
  consolidated list of recurring mistakes and the correct patterns.

- [Debugging Guide](appendices/debugging.md) — practical techniques for
  diagnosing blocked loops, task leaks, timeout failures, and more.

[asyncio]: https://docs.python.org/3/library/asyncio.html
[official-asyncio-documentation]: https://docs.python.org/3/library/asyncio.html
[async]: https://docs.python.org/3/reference/compound_stmts.html#async-def
[await]: https://docs.python.org/3/reference/expressions.html#await
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[asyncio-taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[event]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event
[queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[asyncio-to-thread]: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
[asyncio-runner]: https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner
[asyncio-future]: https://docs.python.org/3/library/asyncio-future.html#asyncio.Future
[asyncio-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task
[trio-docs]: https://trio.readthedocs.io/en/stable/
