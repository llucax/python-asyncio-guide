---
title: Beyond the Basics
description: >-
  Advanced application-level asyncio patterns -- integrating blocking code,
  shielding critical work from cancellation, custom context managers,
  advanced coordination primitives, subprocesses, and the Runner API.
icon: lucide/book-open
---

# Beyond the Basics

This chapter covers patterns you will reach for once you are comfortable with
[The Basics](../the-basics/index.md). Everything here is still
application-level code -- no event loop internals, no framework plumbing.
These are the recipes and tools that fill the gap between "I can write a
TaskGroup" and "I can build a production async service."

If a pattern here feels slippery, bounce back to
[Concurrent Tasks](../the-basics/concurrent-tasks.md),
[Cancellation and Timeouts](../the-basics/cancellation-and-timeouts.md), and
[Resource Management](../the-basics/resource-management.md). When you want the
machinery underneath, continue to
[How Asyncio Works](../how-asyncio-works/index.md), especially
[Tasks and Futures](../how-asyncio-works/tasks-and-futures.md).

This chapter mixes two kinds of sections:

- **Pattern sections** that stay fully guide-owned, such as blocking code,
  shielding, and context-manager design.
- **Reference companion sections** that stay deliberately short when the
  official docs already explain an API well. Those sections focus on when to
  reach for the
  tool, the main pitfall, and where to read the full reference next.

## Sections

1. [Blocking Code](blocking-code.md) -- [`asyncio.to_thread()`][asyncio-to-thread],
   [`loop.run_in_executor()`][loop-run-in-executor] with
   [`ProcessPoolExecutor`][processpoolexecutor], and when to reach for each.

2. [Shielding](shielding.md) -- [`asyncio.shield()`][asyncio-shield], when it is
   actually useful, and how to use it without creating orphaned tasks.

3. [Custom Context Managers](custom-context-managers.md) --
   [`@asynccontextmanager`][at-asynccontextmanager], [`AsyncExitStack`][asyncexitstack], and patterns for composing async
   resource lifetimes.

4. [Advanced Coordination](advanced-coordination.md) -- [`Condition`][condition],
    [`Barrier`][barrier], [`BoundedSemaphore`][boundedsemaphore],
    [`PriorityQueue`][priorityqueue], [`LifoQueue`][lifoqueue]. This is a
    reference companion section.

5. [Subprocesses](subprocesses.md) --
   [`asyncio.create_subprocess_exec()`][asyncio-create-subprocess-exec],
   [`asyncio.create_subprocess_shell()`][asyncio-create-subprocess-shell], and
   the key deadlock and shell-safety rules. This is a reference companion
   section.

6. [Runner](runner.md) -- [`asyncio.Runner`][asyncio-runner] for running
   multiple top-level coroutines in sequence, testing, and REPL use. This is a
   reference companion section.

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
[at-asynccontextmanager]: https://docs.python.org/3/library/contextlib.html#contextlib.asynccontextmanager
[asyncexitstack]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack
