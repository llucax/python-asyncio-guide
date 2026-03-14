---
title: Beyond the Basics
description: >-
  Application-level asyncio patterns beyond the core toolkit -- integrating
  blocking code, shielding critical work from cancellation, custom context
  managers, less-common coordination tools, subprocesses, and the Runner API.
icon: lucide/workflow
---

# Beyond the Basics

This chapter covers patterns you will reach for once you are comfortable with
[The Basics](../the-basics/index.md). Everything here is still
application-level code -- no event loop internals, no framework plumbing.
These are the recipes and tools that fill the gap between "I can write a
[`TaskGroup`](../the-basics/concurrent-tasks.md#asynciotaskgroup)" and
"I can build a production async service."

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

1. [Blocking Code](blocking-code.md) --
   [`asyncio.to_thread()`](blocking-code.md#asyncioto_thread),
   [CPU-bound work with `ProcessPoolExecutor`](blocking-code.md#processpoolexecutor),
   and [when to use what](blocking-code.md#when-to-use-what).

2. [Shielding](shielding.md) --
   [safe shielding patterns](shielding.md#safe-patterns),
   [when to use shielding](shielding.md#when-to-use-shielding), and how to use
   it without creating orphaned tasks.

3. [Custom Context Managers](custom-context-managers.md) --
   [`@asynccontextmanager`](custom-context-managers.md#asynccontextmanager),
   [`AsyncExitStack`](custom-context-managers.md#asyncexitstack), and
   [composing lifetimes](custom-context-managers.md#composing-lifetimes).

4. [Advanced Coordination](advanced-coordination.md) --
   [`Lock`](advanced-coordination.md#asynciolock),
   [`Condition`](advanced-coordination.md#asynciocondition),
   [`Barrier`](advanced-coordination.md#asynciobarrier),
   [`BoundedSemaphore`](advanced-coordination.md#asyncioboundedsemaphore), and
   [`PriorityQueue`/`LifoQueue`](advanced-coordination.md#priorityqueue-and-lifoqueue).
   This is a reference companion section.

5. [Subprocesses](subprocesses.md) --
   [exec vs shell](subprocesses.md#exec-vs-shell),
   [the `communicate()` pattern](subprocesses.md#the-default-pattern-communicate),
   and [pipe deadlocks](subprocesses.md#the-main-pitfall-pipe-deadlocks). This
   is a reference companion section.

6. [Runner](runner.md) --
   [when to use `Runner`](runner.md#when-to-use-runner),
   [the shape of the API](runner.md#the-shape-of-the-api), and
   [cleanup](runner.md#cleanup). This is a reference companion section.
