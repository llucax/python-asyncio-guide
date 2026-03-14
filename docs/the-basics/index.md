---
title: The Basics
description: >-
  Everything you need to write simple but correct and robust async programs --
  coroutines, concurrent tasks, cancellation, timeouts, resource management,
  networking, and inter-task coordination using safe, high-level APIs.
icon: lucide/book-open
---

# The Basics

This chapter covers everything you need to write simple but correct and robust
async programs. By the end, you will be comfortable with coroutines, concurrent
tasks, cancellation, timeouts, resource management, networking, and simple
inter-task coordination -- all using safe, high-level APIs.

The goal here is to teach you how to think about asyncio. For the few API-heavy
areas -- especially streams and synchronization primitives -- the individual
sections link out to the official docs for full method-by-method reference.

## Sections

1. [Getting Started](getting-started.md) -- [`async`][async]/[`await`][await],
   coroutines, [`asyncio.run()`][asyncio-run], [`asyncio.sleep()`][asyncio-sleep],
   and checkpoints.

2. [Concurrent Tasks](concurrent-tasks.md) -- [`TaskGroup`][taskgroup],
   structured concurrency, [`ExceptionGroup`][exceptiongroup], and [`except*`][except].

3. [Cancellation and Timeouts](cancellation-and-timeouts.md) --
   [`CancelledError`][cancellederror], [`asyncio.timeout()`][asyncio-timeout],
   and how they interact with [`TaskGroup`][taskgroup].

4. [Resource Management](resource-management.md) -- [`async with`][async-with],
   [`try`][try]/[`finally`][finally], async generators, and
   [`contextlib.aclosing()`][contextlib-aclosing].

5. [Streams](streams.md) -- [`asyncio.open_connection()`][asyncio-open-connection],
   [`asyncio.start_server()`][asyncio-start-server], backpressure, and the
   stream cleanup rules.

6. [Coordination](coordination.md) -- [`asyncio.Queue`][asyncio-queue],
   [`Event`][event], [`Semaphore`][semaphore], and producer/consumer patterns.

7. [Building a Pipeline](building-a-pipeline.md) -- an actor-based pipeline
   combining [`TaskGroup`][taskgroup], bounded queues, sentinels, fan-out, and
   error handling into a realistic application.

8. [Debugging](debugging.md) -- debug mode, common mistakes, and the
   checkpoint contract (condensed).

[create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[async]: https://docs.python.org/3/reference/compound_stmts.html#async-def
[await]: https://docs.python.org/3/reference/expressions.html#await
[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[asyncio-sleep]: https://docs.python.org/3/library/asyncio-task.html#asyncio.sleep
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[exceptiongroup]: https://docs.python.org/3/library/builtins.html#ExceptionGroup
[except]: https://docs.python.org/3/reference/compound_stmts.html#the-try-statement
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[asyncio-timeout-at]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout_at
[contextlib-aclosing]: https://docs.python.org/3/library/contextlib.html#contextlib.aclosing
[asyncio-open-connection]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_connection
[asyncio-start-server]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.start_server
[asyncio-queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[event]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event
[semaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
[try]: https://docs.python.org/3/reference/compound_stmts.html#the-try-statement
[wait-for]: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for
[async-with]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[finally]: https://docs.python.org/3/reference/compound_stmts.html#the-try-statement
