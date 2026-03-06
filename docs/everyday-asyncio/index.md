# Everyday Asyncio

Previous: [Guide Index](../index.md)
Next: [Beyond the Basics](../beyond-the-basics/index.md)

This chapter covers everything you need to write correct, robust async
programs. By the end, you will be comfortable with coroutines, concurrent
tasks, cancellation, timeouts, resource management, networking, and
inter-task coordination — all using safe, high-level APIs.

No low-level event loop manipulation, no `create_task()`, no `wait_for()`.
Those exist, but you don't need them here, and reaching for them too early is
where most asyncio bugs come from.

## Sections

1. [Getting Started](getting-started.md) — `async`/`await`, coroutines,
   `asyncio.run()`, `asyncio.sleep()`, the async sandwich, and checkpoints.

2. [Concurrent Tasks](concurrent-tasks.md) — `TaskGroup`, structured
   concurrency, `ExceptionGroup`, and `except*`.

3. [Cancellation and Timeouts](cancellation-and-timeouts.md) —
   `CancelledError`, `asyncio.timeout()`, `asyncio.timeout_at()`, and how
   they interact with `TaskGroup`.

4. [Resource Management](resource-management.md) — `async with`,
   `try`/`finally`, `contextlib.aclosing()`, and async generators.

5. [Streams](streams.md) — `asyncio.open_connection()`,
   `asyncio.start_server()`, `StreamReader`, `StreamWriter`.

6. [Coordination](coordination.md) — `asyncio.Queue`, `Lock`, `Event`,
   `Semaphore`, and producer/consumer patterns.

7. [Building a Pipeline](building-a-pipeline.md) — an actor-based pipeline
   combining `TaskGroup`, bounded queues, sentinels, fan-out, and error
   handling into a realistic application.

8. [Debugging](debugging.md) — debug mode, common mistakes, and the
   checkpoint contract (condensed).
