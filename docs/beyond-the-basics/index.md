---
title: Beyond the Basics
description: >-
  Advanced application-level asyncio patterns — integrating blocking code,
  shielding critical work from cancellation, custom context managers,
  advanced coordination primitives, subprocesses, and the Runner API.
icon: lucide/book-open
---

# Beyond the Basics

This chapter covers patterns you will reach for once you are comfortable with
the material in Chapter 1. Everything here is still application-level code --
no event loop internals, no framework plumbing. These are the recipes and
tools that fill the gap between "I can write a TaskGroup" and "I can build a
production async service."

## Sections

1. [Blocking Code](blocking-code.md) — [`asyncio.to_thread()`][asyncio-to-thread],
   [`loop.run_in_executor()`][loop-run-in-executor] with [`ProcessPoolExecutor`][processpoolexecutor], and when to reach for
   each.

2. [Shielding](shielding.md) — [`asyncio.shield()`][asyncio-shield], when it is actually useful,
   and how to use it without creating orphaned tasks.

3. [Custom Context Managers](custom-context-managers.md) —
   `@asynccontextmanager`, `AsyncExitStack`, and patterns for composing async
   resource lifetimes.

4. [Advanced Coordination](advanced-coordination.md) — [`Condition`][condition], [`Barrier`][barrier],
   [`BoundedSemaphore`][boundedsemaphore], [`PriorityQueue`][priorityqueue], [`LifoQueue`][lifoqueue].

5. [Subprocesses](subprocesses.md) — [`asyncio.create_subprocess_exec()`][asyncio-create-subprocess-exec],
   [`asyncio.create_subprocess_shell()`][asyncio-create-subprocess-shell], and working with stdin/stdout/stderr.

6. [Runner](runner.md) — [`asyncio.Runner`][asyncio-runner] for running multiple top-level
   coroutines in sequence, testing, and REPL use.

[asyncio-to-thread]: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
[loop-run-in-executor]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor
[processpoolexecutor]: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ProcessPoolExecutor
[asyncio-shield]: https://docs.python.org/3/library/asyncio-task.html#asyncio.shield
[condition]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition
[barrier]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier
[boundedsemaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.BoundedSemaphore
[priorityqueue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.PriorityQueue
[lifoqueue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.LifoQueue
[asyncio-create-subprocess-exec]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_exec
[asyncio-create-subprocess-shell]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_shell
[asyncio-runner]: https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner