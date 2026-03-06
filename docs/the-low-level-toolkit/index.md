# The Low-Level Toolkit

Previous: [How Asyncio Works](../03-how-asyncio-works/index.md)
Next: [Appendices](../appendices/checkpoint-contract.md)

This chapter is for library and framework authors who need to build on top of
asyncio's low-level APIs. If you are writing application code, you almost
certainly do not need anything here -- Chapters 1 and 2 cover everything an
application needs. But if you are building a connection pool, a protocol
implementation, a task scheduler, or a bridge between asyncio and another
concurrency framework, these are your tools.

Everything in this chapter is "unsafe" in the sense that it bypasses the
structured concurrency guarantees that make the Chapter 1 APIs reliable. Using
these APIs correctly requires understanding the material in Chapter 3.

## Sections

1. [Loop Access and Inspection](loop-access-and-inspection.md) —
   `asyncio.get_running_loop()`, loop introspection, and when you need the
   loop object directly.

2. [Task Coordination](task-coordination.md) — `asyncio.wait()`,
   `asyncio.as_completed()`, `asyncio.wait_for()`, and manual task management.

3. [Futures](futures.md) — `loop.create_future()`, `asyncio.wrap_future()`,
   manual result resolution, and bridging `concurrent.futures`.

4. [Callbacks and Threading](callbacks-and-threading.md) —
   `add_done_callback()`, `loop.call_soon_threadsafe()`,
   `asyncio.run_coroutine_threadsafe()`, signal handling.

5. [Transports and Protocols](transports-and-protocols.md) — the callback-based
   networking layer underneath streams, and when to use it.
