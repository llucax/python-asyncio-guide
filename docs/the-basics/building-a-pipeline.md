---
title: Building a Pipeline
description: >-
  Tie together TaskGroup, queues, backpressure, cancellation, and resource
  management into a realistic actor-based pipeline. Build a production-quality
  async data processing design from scratch.
---

# Building a Pipeline

This section ties together everything from this chapter --
[`TaskGroup`][taskgroup],
[queues](coordination.md#asyncioqueue), backpressure, cancellation,
and [resource management](resource-management.md) -- into a single,
realistic application. We will build an **actor-based pipeline** where
independent async tasks communicate through queues, incrementally
adding concerns until we have a production-quality design.

No network I/O, no external dependencies. Everything runs in a single
process.

## The Actor Model in One Paragraph

An *actor* is a task that owns a loop: it reads messages from an input
queue, does some work, and writes results to an output queue. Actors
don't share mutable state -- they communicate by passing messages. You
wire actors together into a pipeline, and the queues between them act
as both communication channels and flow-control boundaries.

This pattern shows up everywhere: HTTP request processing pipelines,
ETL data flows, log aggregation, chat message routing. The example
here is small, but the shape is the same.

## The Pipeline

We will build three actors:

```mermaid
flowchart LR
    Generator -- queue --> Processor
    Processor -- queue --> Aggregator
```

- **Generator** produces items (numbers) and pushes them into the
  first queue.
- **Processor** reads items, transforms them (squares each number),
  and pushes results into the second queue.
- **Aggregator** collects results and produces a final summary.

We will build this incrementally, adding one concern at a time.

## Step 1: The Simplest Pipeline

Start with the most straightforward version: unbounded queues, no
error handling, one actor of each type.

Key APIs:

- [`asyncio.Queue`][asyncio-queue]
- [`asyncio.TaskGroup`][asyncio-taskgroup]

```python title="pipeline_v1.py"
import asyncio


async def generator(out: asyncio.Queue[int | None]) -> None:
    for i in range(1, 6):
        await out.put(i)
        print(f"  generator: sent {i}")
    await out.put(None)  # signal: no more items


async def processor(
    inp: asyncio.Queue[int | None],
    out: asyncio.Queue[int | None],
) -> None:
    while True:
        item: int | None = await inp.get()
        if item is None:
            await out.put(None)  # propagate the shutdown signal
            return
        result: int = item * item
        await out.put(result)
        print(f"  processor: {item} -> {result}")


async def aggregator(inp: asyncio.Queue[int | None]) -> list[int]:
    results: list[int] = []
    while True:
        item: int | None = await inp.get()
        if item is None:
            return results
        results.append(item)
        print(f"  aggregator: collected {item}")


async def main() -> None:
    q1: asyncio.Queue[int | None] = asyncio.Queue()
    q2: asyncio.Queue[int | None] = asyncio.Queue()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(generator(q1))
        tg.create_task(processor(q1, q2))
        aggregator_task = tg.create_task(aggregator(q2))

    print(f"final results: {aggregator_task.result()}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python pipeline_v1.py"
  generator: sent 1
  generator: sent 2
  generator: sent 3
  generator: sent 4
  generator: sent 5
  processor: 1 -> 1
  processor: 2 -> 4
  processor: 3 -> 9
  processor: 4 -> 16
  processor: 5 -> 25
  aggregator: collected 1
  aggregator: collected 4
  aggregator: collected 9
  aggregator: collected 16
  aggregator: collected 25
final results: [1, 4, 9, 16, 25]
```

A few things to notice:

- **`None` as a sentinel.** Each actor watches for `None` and
  propagates it downstream. This is the simplest shutdown protocol:
  the generator decides when work is done. (Recall the sentinel
  pattern from [Coordination](coordination.md#queue-shutdown-patterns).)
- **[`TaskGroup`][taskgroup] owns all the actors.** The `async with` block doesn't
  exit until every actor has returned. No task can leak. (See
  [Concurrent Tasks](concurrent-tasks.md#asynciotaskgroup) for why
  this matters.)
- **The aggregator's return value** is available via [`task.result()`][task-result]
  after the group finishes.

This works, but the queues are unbounded. If the generator is fast
and the processor is slow, items pile up in memory with no limit.

## Step 2: Backpressure With Bounded Queues

Making a queue bounded is a one-line change, but the effect is
important: when a queue is full, `await queue.put(item)` *suspends
the caller* until the consumer makes room. That is backpressure --
the fast producer automatically slows down to match the slow consumer.
(See [Coordination — Backpressure](coordination.md#backpressure) for
the concept in detail.)

Let's add a simulated delay to the processor so the speed difference
is visible:

```python title="pipeline_v2.py"
import asyncio


async def generator(out: asyncio.Queue[int | None]) -> None:
    for i in range(1, 11):
        await out.put(i)
        print(f"  generator: sent {i}")
    await out.put(None)


async def processor(
    inp: asyncio.Queue[int | None],
    out: asyncio.Queue[int | None],
) -> None:
    while True:
        item: int | None = await inp.get()
        if item is None:
            await out.put(None)
            return
        await asyncio.sleep(0.1)  # simulate slow work
        result: int = item * item
        await out.put(result)
        print(f"  processor: {item} -> {result}")


async def aggregator(inp: asyncio.Queue[int | None]) -> list[int]:
    results: list[int] = []
    while True:
        item: int | None = await inp.get()
        if item is None:
            return results
        results.append(item)
        print(f"  aggregator: collected {item}")


async def main() -> None:
    q1: asyncio.Queue[int | None] = asyncio.Queue(maxsize=2)
    q2: asyncio.Queue[int | None] = asyncio.Queue(maxsize=2)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(generator(q1))
        tg.create_task(processor(q1, q2))
        task = tg.create_task(aggregator(q2))

    print(f"final results: {task.result()}")


if __name__ == "__main__":
    asyncio.run(main())
```

The interleaving in the output shows the backpressure at work:

```text title="$ python pipeline_v2.py"
  generator: sent 1
  generator: sent 2
  generator: sent 3
  processor: 1 -> 1
  generator: sent 4
  aggregator: collected 1
  processor: 2 -> 4
  generator: sent 5
  aggregator: collected 4
  processor: 3 -> 9
  generator: sent 6
  aggregator: collected 9
  processor: 4 -> 16
  generator: sent 7
  aggregator: collected 16
  processor: 5 -> 25
  generator: sent 8
  aggregator: collected 25
  processor: 6 -> 36
  generator: sent 9
  aggregator: collected 36
  processor: 7 -> 49
  generator: sent 10
  aggregator: collected 49
  processor: 8 -> 64
  aggregator: collected 64
  processor: 9 -> 81
  aggregator: collected 81
  processor: 10 -> 100
  aggregator: collected 100
final results: [1, 4, 9, 16, 25, 36, 49, 64, 81, 100]
```

The generator can only get a couple of items ahead before it has to
wait. Memory usage stays bounded no matter how many items flow through
the pipeline. This is the same mechanism that prevents a fast network
sender from overwhelming a slow receiver -- just without the network.

The `maxsize` you choose is a tuning knob. Smaller means tighter
memory bounds but more context-switching between actors. Larger means
more buffering but fewer suspensions.

!!! tip "Trio users"

    [Trio][trio-docs]'s [`trio.open_memory_channel()`][trio-open-memory-channel] requires a max
    buffer size at creation time -- there is no "unbounded" default.
    asyncio's [`Queue`][queue] defaults to unbounded (`maxsize=0`), which is why
    you must be disciplined about always passing `maxsize`.

## Step 3: Error Handling

What happens when an actor crashes? With [`TaskGroup`][taskgroup], the answer is
clean and predictable: the group cancels all sibling tasks and raises
an
[`ExceptionGroup`][exceptiongroup]
containing the failure. (See
[Cancellation and Timeouts](cancellation-and-timeouts.md) for why
this works.)

Let's make the processor blow up on a specific input:

```python title="pipeline_v3.py"
import asyncio


async def generator(out: asyncio.Queue[int | None]) -> None:
    for i in range(1, 6):
        await out.put(i)
        print(f"  generator: sent {i}")
    await out.put(None)


async def processor(
    inp: asyncio.Queue[int | None],
    out: asyncio.Queue[int | None],
) -> None:
    while True:
        item: int | None = await inp.get()
        if item is None:
            await out.put(None)
            return
        if item == 3:
            raise ValueError(f"processor cannot handle {item}")
        result: int = item * item
        await out.put(result)
        print(f"  processor: {item} -> {result}")


async def aggregator(inp: asyncio.Queue[int | None]) -> list[int]:
    results: list[int] = []
    while True:
        item: int | None = await inp.get()
        if item is None:
            return results
        results.append(item)
        print(f"  aggregator: collected {item}")


async def main() -> None:
    q1: asyncio.Queue[int | None] = asyncio.Queue(maxsize=2)
    q2: asyncio.Queue[int | None] = asyncio.Queue(maxsize=2)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(generator(q1))
            tg.create_task(processor(q1, q2))
            tg.create_task(aggregator(q2))
    except* ValueError as eg:
        for exc in eg.exceptions:
            print(f"caught: {exc}")
    else:
        print("pipeline completed without errors")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python pipeline_v3.py"
  generator: sent 1
  generator: sent 2
  generator: sent 3
  processor: 1 -> 1
  aggregator: collected 1
  processor: 2 -> 4
  aggregator: collected 4
caught: processor cannot handle 3
```

Here is what happened:

1. The processor raised `ValueError` when it saw `3`.
2. [`TaskGroup`][taskgroup] cancelled the generator and the aggregator.
3. The [`except*`][except] clause caught the `ValueError` wrapped in an
   [`ExceptionGroup`][exceptiongroup].

No task leaked. No error was silently swallowed. The generator didn't
keep pumping items into a queue that nobody was reading. This is
exactly the behaviour you want in a production pipeline: fail fast,
fail visibly, clean up everything.

## Step 4: Full Pipeline With Clean Shutdown

Now let's put it all together into a more complete version. This
version adds:

- **Type-safe sentinel handling** with a dedicated sentinel type
  instead of `None`
- **Logging** instead of bare `print`, so you can see timestamps and
  actor names
- **Graceful shutdown** that drains in-flight work
- **Multiple processors** running in parallel to demonstrate fan-out

```python title="pipeline_v4.py"
from __future__ import annotations

import asyncio
import logging
from typing import TypeAlias, assert_never


# -- Stop sentinel type for clean shutdown --


class Stop:
    pass

Message: TypeAlias = int | Stop


# -- Actors --


async def generator(
    out: asyncio.Queue[Message],
    count: int,
) -> None:
    log = logging.getLogger("generator")
    for i in range(1, count + 1):
        await out.put(i)
        log.info("sent %d", i)
        await asyncio.sleep(0.01)  # simulate production delay
    await out.put(Stop())
    log.info("done, sent stop signal")


async def processor(
    name: str,
    inp: asyncio.Queue[Message],
    out: asyncio.Queue[Message],
) -> None:
    log = logging.getLogger(name)
    while True:
        item: Message = await inp.get()
        match item:
            case Stop() as stop:
                # Put the sentinel back so sibling processors
                # also see it.
                await inp.put(stop)
                log.info("shutting down")
                return
            case int():
                await asyncio.sleep(0.05)  # simulate work
                result: int = item * item
                await out.put(result)
                log.info("%d -> %d", item, result)
            case unexpected:
                log.error("unexpected message: %s", unexpected)
                assert_never(unexpected)


async def aggregator(
    inp: asyncio.Queue[Message],
) -> list[int]:
    log = logging.getLogger("aggregator")
    results: list[int] = []
    while True:
        item: Message = await inp.get()
        match item:
            case Stop():
                log.info(
                    "done, collected %d results", len(results)
                )
                return results
            case int():
                results.append(item)
                log.info(
                    "collected %d (total: %d)",
                    item,
                    len(results),
                )
            case unexpected:
                log.error("unexpected message: %s", unexpected)
                assert_never(unexpected)


async def processor_supervisor(
    num_workers: int,
    inp: asyncio.Queue[Message],
    out: asyncio.Queue[Message],
) -> None:
    """Run multiple processors; send one stop to aggregator."""
    async with asyncio.TaskGroup() as tg:
        for i in range(num_workers):
            tg.create_task(
                processor(f"processor-{i}", inp, out)
            )

    # All processors have stopped. Send one stop downstream.
    await out.put(Stop())


# -- Main --


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-14s  %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("pipeline")

    q_in: asyncio.Queue[Message] = asyncio.Queue(maxsize=4)
    q_out: asyncio.Queue[Message] = asyncio.Queue(maxsize=4)

    num_items: int = 12
    num_workers: int = 3

    log.info(
        "starting pipeline: %d items, %d workers",
        num_items,
        num_workers,
    )

    async with asyncio.TaskGroup() as tg:
        tg.create_task(generator(q_in, num_items))
        tg.create_task(
            processor_supervisor(num_workers, q_in, q_out)
        )
        result_task = tg.create_task(aggregator(q_out))

    results: list[int] = result_task.result()
    log.info("pipeline complete: %d results", len(results))
    log.info("results: %s", results)


if __name__ == "__main__":
    asyncio.run(main())
```

Timestamps and interleaving will vary, but output looks like this:

```text title="$ python pipeline_v4.py"
12:00:00  pipeline        starting pipeline: 12 items, 3 workers
12:00:00  generator       sent 1
12:00:00  generator       sent 2
12:00:00  generator       sent 3
12:00:00  generator       sent 4
12:00:00  generator       sent 5
12:00:00  processor-0     1 -> 1
12:00:00  processor-1     2 -> 4
12:00:00  processor-2     3 -> 9
12:00:00  generator       sent 6
12:00:00  generator       sent 7
12:00:00  generator       sent 8
12:00:00  aggregator      collected 1 (total: 1)
12:00:00  aggregator      collected 4 (total: 2)
12:00:00  aggregator      collected 9 (total: 3)
12:00:00  processor-0     4 -> 16
12:00:00  processor-1     5 -> 25
12:00:00  processor-2     6 -> 36
12:00:00  generator       sent 9
12:00:00  generator       sent 10
12:00:00  generator       sent 11
12:00:00  aggregator      collected 16 (total: 4)
12:00:00  aggregator      collected 25 (total: 5)
12:00:00  aggregator      collected 36 (total: 6)
12:00:00  processor-0     7 -> 49
12:00:00  processor-1     8 -> 64
12:00:00  processor-2     9 -> 81
12:00:00  generator       sent 12
12:00:00  generator       done, sent stop signal
12:00:00  aggregator      collected 49 (total: 7)
12:00:00  aggregator      collected 64 (total: 8)
12:00:00  aggregator      collected 81 (total: 9)
12:00:00  processor-0     10 -> 100
12:00:00  processor-1     11 -> 121
12:00:00  processor-2     12 -> 144
12:00:00  processor-0     shutting down
12:00:00  processor-1     shutting down
12:00:00  processor-2     shutting down
12:00:00  aggregator      collected 100 (total: 10)
12:00:00  aggregator      collected 121 (total: 11)
12:00:00  aggregator      collected 144 (total: 12)
12:00:00  aggregator      done, collected 12 results
12:00:00  pipeline        pipeline complete: 12 results
12:00:00  pipeline        results: [1, 4, 9, 16, 25, 36, 49, 64, 81, 100, 121, 144]
```

Let's walk through the design decisions.

### Sentinel type instead of `None`

In Step 1 we used `None` as the shutdown signal. That works when your
payload type doesn't include `None`, but it is fragile -- if the
pipeline ever carries optional values, the sentinel collides with
legitimate data. The `Stop` sentinel class is unambiguous: no real
payload will ever be `Stop`.

The type alias `Message = int | Stop` makes the intent explicit. The
queue type `asyncio.Queue[Message]` tells mypy (and the reader)
exactly what can flow through the channel. In a real application you
would define a separate alias per pipeline (or use a generic
`TypeVar`) -- keeping it concrete here makes the example easier to
follow.

### Fan-out with multiple processors

The generator puts items into a shared input queue. Three processor
tasks pull from that same queue. Because
[`asyncio.Queue.get()`][asyncio-queue-get]
is atomic from the perspective of the event loop (only one awaiting
task gets each item), there is no duplication -- items are distributed
across workers automatically.

The shutdown protocol for fan-out needs care. When a processor sees
`Stop`, it puts the sentinel *back* into the input queue so that
sibling processors also see it and shut down in turn. The
supervisor's [`TaskGroup`][taskgroup] waits for all processors to finish, then
sends a single `Stop` to the output queue for the aggregator.

### Nested [`TaskGroup`][taskgroup] for the supervisor

The `processor_supervisor` function uses its own
[`TaskGroup`][taskgroup]
to manage the processor pool. This is structured concurrency in
action: the supervisor is itself a task in the outer group, and it
owns the lifetimes of its processors. If any processor crashes, the
supervisor's [`TaskGroup`][taskgroup] cancels the other processors, and then the
supervisor itself propagates the error to the outer group, which
cancels the generator and aggregator.

Two levels of [`TaskGroup`][taskgroup], each responsible for its own children. No
cleanup code required -- the structure handles it. (See
[Resource Management](resource-management.md) for more on how
`async with` guarantees cleanup.)

## Common Failure Modes

!!! warning

    Watch out for these common failure modes -- each one can cause
    subtle, hard-to-debug problems in production:

    - **Task leaks.** Creating tasks with [`asyncio.create_task()`][asyncio-create-task]
      outside a [`TaskGroup`][taskgroup] and losing the reference. Prefer [`TaskGroup`][taskgroup]
      for anything with a defined lifetime.
    - **Swallowed cancellation.** Catching
      [`CancelledError`][cancellederror]
      and continuing work instead of letting it propagate. See
      [Cancellation and Timeouts](cancellation-and-timeouts.md) for the
      details.
    - **Unbounded queues.** Forgetting to set `maxsize` and wondering
      why memory keeps growing under load.
    - **Sentinel collisions.** Using `None` as a sentinel in queues
      that carry optional data. Use a dedicated type.
    - **Blocking the event loop.** Calling `time.sleep()`, running
      CPU-heavy computation, or doing synchronous I/O inside an
      `async def`. The event loop can't schedule other tasks while
      you are blocking.

## Beyond This Example

The actor pipeline we built here is intentionally self-contained --
no network, no files, no external services. But the same patterns
apply directly to real-world systems:

- **HTTP request pipelines.** Replace the generator with an async
  HTTP client fetching URLs, the processor with response parsing
  logic, and the aggregator with a database writer.
- **Data processing.** Read records from a file or stream, transform
  them in parallel, write results to another destination. Bounded
  queues keep memory predictable.
- **Chat and messaging systems.** Each connected client gets an
  outgoing queue. A broadcast actor reads messages and fans them out.
  The same backpressure and shutdown patterns apply.
- **Task orchestration.** Queue-based actor pipelines are a natural
  fit for workflow engines where each stage has different resource
  requirements or failure modes.

The core ideas -- actors as tasks, queues as channels, [`TaskGroup`][taskgroup]
as the lifetime manager, sentinels for shutdown -- scale from toy
examples to production systems without changing shape.

---

[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[asyncio-queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[asyncio-taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[task-result]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.result
[queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[exceptiongroup]: https://docs.python.org/3/library/builtins.html#ExceptionGroup
[except]: https://docs.python.org/3/reference/compound_stmts.html#the-try-statement
[asyncio-queue-get]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get
[asyncio-create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[trio-docs]: https://trio.readthedocs.io/en/stable/
[trio-open-memory-channel]: https://trio.readthedocs.io/en/stable/reference-core.html#trio.open_memory_channel
