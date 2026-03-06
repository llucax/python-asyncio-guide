---
title: "Asyncio: A Concept-First Learning Guide"
description: >-
  A structured, concept-first guide to Python's asyncio library. Learn
  async/await from the ground up with modern, structured concurrency
  patterns targeting Python 3.11+.
---

# Asyncio: A Concept-First Learning Guide

This is a general-purpose learning guide for Python's built-in `asyncio`.

The structure and teaching style are inspired by
[Trio's excellent documentation](https://trio.readthedocs.io/en/stable/).
Trio deliberately designs for structured concurrency and cancellation
ergonomics. If you can adopt Trio, it is often a great choice. But many
codebases cannot switch away from the standard library. `asyncio` is widely
deployed, and this guide aims to fill the gap in high-quality learning
resources for it.

This guide complements the
[official asyncio documentation](https://docs.python.org/3/library/asyncio.html);
it does not replace it. When this guide mentions a concrete `asyncio` API, it
links to the corresponding page in the Python docs.

## Who This Is For

- You know Python, but `async`/`await` still feels slippery.
- You've written small `asyncio` snippets, or just simple async functions
  filling the gaps when using a framework (like a web framework), and now need
  full, robust, maintainable async programs.
- You want modern, structured patterns (`TaskGroup`, timeouts, explicit
  lifetimes).

## Prerequisites

You should be comfortable writing and calling Python functions, handling
exceptions, and reading tracebacks. A rough idea of what I/O means (network
requests, reading files) is helpful. You do **not** need prior experience with
threads or event loops -- we build up the mental model from scratch.

### Python Version

This guide assumes **Python 3.11 or newer**. It uses `asyncio.TaskGroup`,
`asyncio.timeout()`, and other modern APIs throughout without version guards.

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

1. [Everyday Asyncio](everyday-asyncio/index.md) — `asyncio.run()`,
   coroutines, `TaskGroup`, `asyncio.timeout()`, `Event`, `Queue`, and
   everything you need for day-to-day async programming.

2. [Beyond the Basics](beyond-the-basics/index.md) — `asyncio.to_thread()`,
   `shield()`, subprocesses, async context managers, advanced synchronization,
   and `asyncio.Runner`.

3. [How Asyncio Works](how-asyncio-works/index.md) — the event loop model,
   `asyncio.Future`, `asyncio.Task`, task lifecycle, and the full cancellation
   mechanics.

4. [The Low-Level Toolkit](the-low-level-toolkit/index.md) —
   `get_running_loop()`, `wait()`, `as_completed()`, `wait_for()`,
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
