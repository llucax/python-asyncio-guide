---
title: The Low-Level Toolkit
description: >-
  Low-level asyncio APIs for library and framework authors. Covers loop
  access, manual task coordination, bare futures, callbacks, threading
  integration, and the transports-and-protocols layer.
icon: lucide/wrench
---

# The Low-Level Toolkit

This chapter is for library and framework authors who need to build on top of
asyncio's low-level APIs. If you are writing application code, you almost
certainly do not need anything here --
[The Basics](../the-basics/index.md) and
[Beyond the Basics](../beyond-the-basics/index.md) cover everything an
application needs. But if you are building a connection pool, a protocol
implementation, a task scheduler, or a bridge between asyncio and another
concurrency framework, these are your tools.

Everything in this chapter is "unsafe" in the sense that it bypasses the
structured concurrency guarantees that make the
[The Basics](../the-basics/index.md) APIs reliable. Using these APIs correctly
requires understanding [How Asyncio Works](../how-asyncio-works/index.md),
especially [The Event Loop](../how-asyncio-works/the-event-loop.md) and
[Tasks and Futures](../how-asyncio-works/tasks-and-futures.md).

This chapter is intentionally lighter than the earlier ones. The stdlib docs
are already strong on many of these APIs, so these sections focus on
orientation:
what the tool is for, when to reach for it, the main footguns, and where to
read the official reference next.

For the application-level boundary cases that usually lead you here, see
[Blocking Code](../beyond-the-basics/blocking-code.md) and
[Runner](../beyond-the-basics/runner.md) first.

## Sections

1. [Loop Access and Inspection](loop-access-and-inspection.md) --
   [the normal `get_running_loop()` accessor](loop-access-and-inspection.md#the-normal-accessor-get_running_loop),
   [when you need the loop object directly](loop-access-and-inspection.md#when-you-actually-need-the-loop),
   and [task inspection](loop-access-and-inspection.md#task-inspection-you-should-remember).
   This is a reference companion section.

2. [Task Coordination](task-coordination.md) --
   [`asyncio.wait()`](task-coordination.md#asynciowait),
   [`asyncio.as_completed()`](task-coordination.md#asyncioas_completed),
   [`asyncio.wait_for()`](task-coordination.md#asynciowait_for), and
   [which tool fits which job](task-coordination.md#which-tool-fits-which-job).
   This is a reference companion section.

3. [Futures](futures.md) --
   [the three operations that matter most](futures.md#the-three-operations-that-matter-most),
   [bridging a callback API](futures.md#canonical-pattern-bridge-a-callback-api),
   and [`wrap_future()`](futures.md#wrap_future). This is a reference companion
   section.

4. [Callbacks and Threading](callbacks-and-threading.md) --
   [`add_done_callback()` and `remove_done_callback()`](callbacks-and-threading.md#add_done_callback-and-remove_done_callback),
   [`call_soon_threadsafe()`](callbacks-and-threading.md#call_soon_threadsafe),
   [`run_coroutine_threadsafe()`](callbacks-and-threading.md#run_coroutine_threadsafe),
   and [signal handling](callbacks-and-threading.md#signal-handling).

5. [Transports and Protocols](transports-and-protocols.md) --
   [the model in one sentence](transports-and-protocols.md#the-model-in-one-sentence),
   [main differences from streams](transports-and-protocols.md#main-differences-from-streams),
   and when to use it. This is a reference companion section.
