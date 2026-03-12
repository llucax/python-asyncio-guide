---
title: The Low-Level Toolkit
description: >-
  Low-level asyncio APIs for library and framework authors. Covers loop
  access, manual task coordination, bare futures, callbacks, threading
  integration, and the transports-and-protocols layer.
icon: lucide/book-open
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
   [`asyncio.get_running_loop()`][asyncio-get-running-loop], loop introspection,
   and when you need the loop object directly. This is a reference companion
   section.

2. [Task Coordination](task-coordination.md) -- [`asyncio.wait()`][asyncio-wait],
   [`asyncio.as_completed()`][asyncio-as-completed],
   [`asyncio.wait_for()`][asyncio-wait-for], and manual task management. This
   is a reference companion section.

3. [Futures](futures.md) -- [`loop.create_future()`][loop-create-future],
   [`asyncio.wrap_future()`][asyncio-wrap-future], manual result resolution, and
   bridging `concurrent.futures`. This is a reference companion section.

4. [Callbacks and Threading](callbacks-and-threading.md) --
   [`add_done_callback()`][add-done-callback], [`loop.call_soon_threadsafe()`][loop-call-soon-threadsafe],
   [`asyncio.run_coroutine_threadsafe()`][asyncio-run-coroutine-threadsafe],
   signal handling.

5. [Transports and Protocols](transports-and-protocols.md) -- the callback-based
   networking layer underneath streams, and when to use it. This is a
   reference companion section.

[asyncio-get-running-loop]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop
[asyncio-wait]: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait
[asyncio-as-completed]: https://docs.python.org/3/library/asyncio-task.html#asyncio.as_completed
[asyncio-wait-for]: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for
[loop-create-future]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_future
[asyncio-wrap-future]: https://docs.python.org/3/library/asyncio-future.html#asyncio.wrap_future
[loop-call-soon-threadsafe]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon_threadsafe
[asyncio-run-coroutine-threadsafe]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run_coroutine_threadsafe
[add-done-callback]: https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.add_done_callback
