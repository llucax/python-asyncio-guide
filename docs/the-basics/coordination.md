---
title: Coordination
description: >-
  Coordinate concurrent tasks with asyncio.Queue, Event, and Semaphore.
  Learn inter-task communication patterns, backpressure with bounded queues,
  startup signaling, and concurrency limits.
---

# Coordination

Up to this point, your concurrent tasks have been independent -- they each do
their own work and you collect the results when the [`TaskGroup`][taskgroup]
finishes. Real programs are rarely that tidy. Tasks need to *talk* to each
other: pass data, wait for signals, or limit how many hit an external API at
once. In simple asyncio programs, the first tools to reach for are
[`Queue`][queue], [`Event`][event], and [`Semaphore`][semaphore].

!!! Info

    This section focuses on the common patterns: bounded queues,
    backpressure, sentinels, startup signaling, and throttling. Use the
    official [Queues][official-queues] and [Synchronization
    Primitives][official-sync] pages for the full API details.

There are more specialized primitives too -- notably [`Lock`][lock],
[`Condition`][condition], [`Barrier`][barrier], and
[`BoundedSemaphore`][boundedsemaphore]. Because asyncio tasks are
cooperative, direct shared-state coordination is more niche here than it is
in threaded code. This chapter stays focused on message passing, signaling,
and bounded concurrency. [Advanced
Coordination](../beyond-the-basics/advanced-coordination.md) in [Beyond the
Basics](../beyond-the-basics/index.md) is the map for the rest.

## `#!py asyncio.Queue`

The *queue* is the primary tool for inter-task communication. Instead of
sharing mutable state directly, you pass messages through a queue. One task
puts items in, another takes them out -- the queue handles all the
synchronisation.

Create a queue with [`asyncio.Queue(maxsize=...)`][asyncio-queue-maxsize].
**Always set `maxsize`** -- you will see why shortly. In beginner code, the
core operations are:

- [`put(item)`][put-item] -- suspend if the queue is full
- [`get()`][get] -- suspend if the queue is empty

Queue also provides [`task_done()`][task-done] and [`join()`][join] for
completion tracking. In structured-concurrency code, that is a more specialized
pattern than basic producer/consumer communication, so this chapter keeps the
focus on communication, backpressure, and shutdown. See [Advanced
Coordination](../beyond-the-basics/advanced-coordination.md#queue-completion-tracking)
when you need an extra "all queued work is finished" checkpoint.

There are also `*_nowait()` methods plus inspection helpers such as
[`qsize()`][qsize] and [`empty()`][empty], but those are best treated as
secondary tools. Use the official queue docs when you need the full API.

Here is a minimal producer/consumer to see the queue in action:

```python title="queue_basic.py"
import asyncio

async def producer(queue: asyncio.Queue[int]) -> None:
    for i in range(5):
        await queue.put(i)
        print(f"Produced: {i}")

async def consumer(queue: asyncio.Queue[int]) -> None:
    for _ in range(5):
        item: int = await queue.get()
        print(f"Consumed: {item}")
        await asyncio.sleep(0.2)  # Simulate processing

async def main() -> None:
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=2)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(queue), name="producer")
        tg.create_task(consumer(queue), name="consumer")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python queue_basic.py"
Produced: 0
Produced: 1
Consumed: 0
Produced: 2
Consumed: 1
Produced: 3
Consumed: 2
Produced: 4
Consumed: 3
Consumed: 4
```

The producer fills the queue to `maxsize=2` and then waits. Each time the
consumer takes an item, the producer wakes up. This is *backpressure*.

## Backpressure

*Backpressure* is what happens when a fast producer meets a slow consumer.
Without a size limit, the producer never blocks and items pile up in memory
without bound -- eventually eating all RAM and crashing the process.

With `maxsize=0` (the default -- unbounded), a producer generating a million
items dumps them all before the consumer processes even a handful. The fix is
trivial -- set `maxsize`:

```python
queue: asyncio.Queue[int] = asyncio.Queue(maxsize=50)
```

Now the producer blocks after 50 items and can only continue as the consumer
drains the queue. Memory stays bounded, and the system adapts to the consumer's
pace.

!!! Warning

    Always set `maxsize`. Start with a small number (10-100) and adjust based
    on observation.

!!! Tip "Trio"

    [Trio][trio-docs]'s
    [`trio.open_memory_channel()`][trio-open-memory-channel] requires a max
    buffer size at creation time -- no "unbounded" default. asyncio's
    [`Queue`][queue] defaults to unbounded, which is why you must be
    disciplined about `maxsize`.

## Queue Shutdown Patterns

Eventually your producers run out of work and your consumers need to know it is
time to stop. In the first queue example, the consumer used `#!py for _ in
range(5):` because we already knew the producer would emit exactly five items,
but it is not a great shutdown pattern. In real code, the consumer usually
should not need to know ahead of time how many items the producer will send.

The simplest fix is a *sentinel value* -- a special item that means "no more
data is coming." Here is the same producer/consumer shape as above, extended so
the producer sends `#!py None` when it is done and the consumer stops when it
receives that sentinel:

```python title="queue_with_sentinel.py" hl_lines="7 11 13-15 20"
import asyncio

async def producer(queue: asyncio.Queue[int | None]) -> None:
    for i in range(5):
        await queue.put(i)
        print(f"Produced: {i}")
    await queue.put(None) # (1)!
    print("Producer: sent stop signal")

async def consumer(queue: asyncio.Queue[int | None]) -> None:
    while True: # (2)!
        item: int | None = await queue.get()
        if item is None: # (3)!
            print("Consumer: stopping")
            return
        print(f"Consumed: {item}")
        await asyncio.sleep(0.2)  # Simulate processing

async def main() -> None:
    queue: asyncio.Queue[int | None] = asyncio.Queue(maxsize=2) # (4)!

    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(queue), name="producer")
        tg.create_task(consumer(queue), name="consumer")

if __name__ == "__main__":
    asyncio.run(main())
```

1. The producer sends `None` to signal shutdown.
2. The consumer now loops *forever* (until it sees the sentinel).
3. The consumer checks for the sentinel and stops when it sees it.
4. The queue type was updated to allow `None` as a valid item to signal shutdown.

```text title="$ python queue_with_sentinel.py"
Produced: 0
Produced: 1
Consumed: 0
Produced: 2
Consumed: 1
Produced: 3
Consumed: 2
Produced: 4
Consumed: 3
Producer: sent stop signal
Consumed: 4
Consumer: stopping
```

The most common sentinel is `#!py None`, but any unique object works. With one
consumer, one sentinel is enough. The critical detail is what happens when you
scale out: **send one sentinel per consumer.** If you have three consumers but
only send one sentinel, two of them will hang forever.

!!! Tip

    If `#!py None` is a valid data value, define a dedicated sentinel. For a
    type-safe stop sentinel you can use `#!py class Stop: pass`. Then `#!py
    match` against `#!py case Stop():` instead of `#!py is None`.

## `asyncio.Event`

An [`Event`][event] is a simple flag that tasks can wait on. It starts unset.
[`event.set()`][event-set] raises the flag, waking all tasks blocked on
[`event.wait()`][event-wait]. The event stays set until you call
[`event.clear()`][event-clear], and you can check its state with
[`event.is_set()`][event-is-set].

The classic use case is startup coordination -- tasks that wait until a service
is ready:

```python title="event_example.py"
import asyncio

async def database_init(ready: asyncio.Event) -> None:
    print("DB: initialising...")
    await asyncio.sleep(1)  # Simulate slow startup
    print("DB: ready")
    ready.set()

async def request_handler(name: str, db_ready: asyncio.Event) -> None:
    await db_ready.wait()
    print(f"{name}: handling request")
    await asyncio.sleep(0.2)
    print(f"{name}: done")

async def main() -> None:
    db_ready = asyncio.Event()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(database_init(db_ready), name="database-init")
        tg.create_task(request_handler("req-1", db_ready), name="req-1")
        tg.create_task(request_handler("req-2", db_ready), name="req-2")
        tg.create_task(request_handler("req-3", db_ready), name="req-3")

if __name__ == "__main__":
    asyncio.run(main())
```

Once the event is set, the exact order in which the handlers wake up can vary.
One run looks like this:

```text title="$ python event_example.py"
DB: initialising...
DB: ready
req-1: handling request
req-2: handling request
req-3: handling request
req-1: done
req-2: done
req-3: done
```

All three handlers blocked on `#!py db_ready.wait()` until `#!py ready.set()`
was called, then woke up simultaneously. Calling `#!py wait()` *after* the
event is already set returns immediately -- no race condition.

!!! Note

    An [`Event`][event] is best suited for *one-shot* or *phase-transition*
    signaling: a resource is ready, a shutdown has been requested,
    initialisation is complete. If you need repeated notifications, a
    [`Queue`][queue] or a [`Condition`][condition] from [Advanced
    Coordination](../beyond-the-basics/advanced-coordination.md) is a better
    fit.

## `asyncio.Semaphore`

A [`Semaphore`][semaphore] limits how many tasks can enter a section of code
concurrently. Create one with a count, and each `#!py async with semaphore:`
decrements it. When it hits zero, the next task suspends until someone exits.

The most common use case is limiting concurrency against an external resource
-- an API, a database connection pool, or a filesystem that chokes under too
many parallel reads:

```python title="semaphore_example.py"
import asyncio

async def fetch_url(sem: asyncio.Semaphore, url: str) -> str:
    async with sem:
        print(f"  Fetching {url}...")
        await asyncio.sleep(0.5)  # Simulate network I/O
        return f"<html>{url}</html>"

async def main() -> None:
    urls: list[str] = [f"https://api.example.com/page/{i}" for i in range(6)]
    sem = asyncio.Semaphore(3)  # At most 3 concurrent fetches

    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(fetch_url(sem, url), name=f"fetch-page-{i}")
            for i, url in enumerate(urls)
        ]

    print(f"Fetched {len([t.result() for t in tasks])} pages")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python semaphore_example.py"
  Fetching https://api.example.com/page/0...
  Fetching https://api.example.com/page/1...
  Fetching https://api.example.com/page/2...
  Fetching https://api.example.com/page/3...
  Fetching https://api.example.com/page/4...
  Fetching https://api.example.com/page/5...
Fetched 6 pages
```

All six tasks were created at once, but the semaphore ensured only three were
active at any given time. This gives you the full concurrency of a
[`TaskGroup`][taskgroup] with a hard cap on how many tasks are doing real work
simultaneously.

!!! Tip "Trio"

    [Trio][trio-docs] has [`trio.CapacityLimiter`][trio-capacity-limiter],
    which works similarly but has stricter ownership semantics. asyncio's
    [`Semaphore`][semaphore] is simpler -- it is just a counter.

!!! Warning

    A [`Semaphore`][semaphore] limits concurrency, not rate. A semaphore with a
    value of 3 means "at most 3 tasks at once," not "3 tasks per second." If
    you need rate limiting, you need a token bucket or leaky bucket algorithm.

## Choosing the Right Tool

When you need tasks to communicate, reach for a **Queue** -- it provides
natural backpressure and makes data flow explicit. When one task needs to
signal others that a condition has been met, use an **Event**. When you want
to limit how many tasks are active at once, use a **Semaphore**. These three
cover the vast majority of beginner coordination needs. If you find yourself
coordinating through shared mutable state instead, see [Advanced
Coordination](../beyond-the-basics/advanced-coordination.md) for
[`Lock`][lock], [`Condition`][condition], and the other more specialized tools.

[asyncio-event]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event
[asyncio-queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[asyncio-queue-maxsize]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[asyncio-semaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
[barrier]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier
[boundedsemaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.BoundedSemaphore
[condition]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition
[empty]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.empty
[event]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event
[event-clear]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.clear
[event-is-set]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.is_set
[event-set]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.set
[event-wait]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.wait
[full]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.full
[get]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get
[get-nowait]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get_nowait
[join]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.join
[lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[official-queues]: https://docs.python.org/3/library/asyncio-queue.html
[official-sync]: https://docs.python.org/3/library/asyncio-sync.html
[put-item]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put
[put-nowait-item]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put_nowait
[qsize]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.qsize
[queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[queueempty]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueEmpty
[queuefull]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueFull
[semaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
[task-done]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[trio-capacity-limiter]: https://trio.readthedocs.io/en/stable/reference-core.html#trio.CapacityLimiter
[trio-docs]: https://trio.readthedocs.io/
[trio-open-memory-channel]: https://trio.readthedocs.io/en/stable/reference-core.html#trio.open_memory_channel
