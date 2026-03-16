---
title: The Basics
description: >-
  Everything you need to write simple but correct and robust async programs --
  coroutines, concurrent tasks, cancellation, timeouts, resource management,
  inter-task coordination, practical pipelines, and debugging.
icon: lucide/graduation-cap
---

# The Basics

This chapter covers everything you need to write simple but correct and robust
async programs. By the end, you will be comfortable with coroutines, concurrent
tasks, cancellation, timeouts, resource management, simple inter-task
coordination, practical pipelines, and debugging -- all using safe,
high-level APIs.

The goal here is to teach you how to think about asyncio. For the more
API-heavy areas, the individual sections link out to the official docs for full
method-by-method reference.

## Sections

1. [Getting Started](getting-started.md) --
   [`await`](getting-started.md#await),
   [the async sandwich](getting-started.md#the-async-sandwich),
   [`asyncio.run()`](getting-started.md#hello-world),
   [`asyncio.sleep()`](getting-started.md#asynciosleep), and
   [checkpoints](getting-started.md#checkpoints).

2. [Concurrent Tasks](concurrent-tasks.md) --
   [`TaskGroup`](concurrent-tasks.md#asynciotaskgroup),
   [structured concurrency](concurrent-tasks.md#structured-concurrency), and
   [`ExceptionGroup` and `except*`](concurrent-tasks.md#exceptiongroup-and-except).

3. [Cancellation and Timeouts](cancellation-and-timeouts.md) --
   [cancellation](cancellation-and-timeouts.md#cancellation),
   [timeouts](cancellation-and-timeouts.md#timeouts), and
   [timeouts in task groups](cancellation-and-timeouts.md#timeouts-and-task-groups).

4. [Resource Management](resource-management.md) --
   [`async with`](resource-management.md#async-context-managers-and-async-with),
   [async generators](resource-management.md#async-generators),
   [async cleanup](resource-management.md#async-cleanup), and
   [`contextlib.aclosing()`](resource-management.md#contextlibaclosing).

5. [Coordination](coordination.md) --
   [`asyncio.Queue`](coordination.md#asyncioqueue),
   [backpressure](coordination.md#backpressure),
   [`asyncio.Event`](coordination.md#asyncioevent), and
   [`asyncio.Semaphore`](coordination.md#asynciosemaphore).

6. [Building a Pipeline](building-a-pipeline.md) -- an actor-based pipeline
   combining
   [bounded queues](building-a-pipeline.md#step-2-backpressure-with-bounded-queues),
   [error handling](building-a-pipeline.md#step-3-error-handling), and
   [clean shutdown](building-a-pipeline.md#step-4-full-pipeline-with-clean-shutdown)
   into a realistic application.

7. [Debugging](debugging.md) --
   [debug mode](debugging.md#debug-mode),
   [common mistakes](debugging.md#common-mistakes-checklist), and the
   [checkpoint contract](debugging.md#checkpoint-contract-condensed).
