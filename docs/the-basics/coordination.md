---
title: Coordination
description: >-
  Coordinate concurrent tasks with asyncio.Queue, Lock, Event, and
  Semaphore. Learn inter-task communication patterns, backpressure with
  bounded queues, and rate limiting.
---

# Coordination

Up to this point, your concurrent tasks have been independent -- they each do
their own work and you collect the results when the [`TaskGroup`][taskgroup] finishes. Real
programs are rarely that tidy. Tasks need to *talk* to each other: pass data,
wait for signals, or limit how many hit an external API at once. asyncio
provides four coordination primitives for these situations:
[`Queue`][queue],
[`Lock`][lock],
[`Event`][event],
and
[`Semaphore`][semaphore].

!!! info

    This page focuses on the patterns: bounded queues, backpressure, sentinels,
    and throttling. Use the official [Queues][official-queues] and
    [Synchronization Primitives][official-sync] pages for the full API details.

## [`asyncio.Queue`][asyncio-queue]

The *queue* is the primary tool for inter-task communication. Instead of
sharing mutable state and protecting it with locks, you pass messages through
a queue. One task puts items in, another takes them out -- the queue handles
all the synchronisation.

Create a queue with
[`asyncio.Queue(maxsize=...)`][asyncio-queue-maxsize].
**Always set `maxsize`** -- you will see why shortly. The core methods come
in two flavours: coroutines that wait, and synchronous variants that raise
immediately if the operation cannot complete.

**Coroutine methods (these are checkpoints):**

- [`put(item)`][put-item]
  -- add an item. If the queue is full, suspends until space is available.
- [`get()`][get]
  -- remove and return an item. If the queue is empty, suspends until an item
  is available.

**Synchronous methods (no [`await`][await], raise on failure):**

- [`put_nowait(item)`][put-nowait-item]
  -- add an item immediately or raise
  [`QueueFull`][queuefull].
- [`get_nowait()`][get-nowait]
  -- get an item immediately or raise
  [`QueueEmpty`][queueempty].

**Inspection:**
[`qsize()`][qsize],
[`empty()`][empty],
[`full()`][full].
These are snapshots -- by the time you act on them, another task may have
changed the queue. Use them for monitoring, not control flow.

**Completion tracking:**
[`task_done()`][task-done]
and [`join()`][join]
-- call [`task_done()`][task-done] after processing each item from [`get()`][get], and [`join()`][join]
blocks until every item has been marked done.

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
        await asyncio.sleep(0.2)  # Simulate processing
        print(f"Consumed: {item}")
        queue.task_done()

async def main() -> None:
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=2)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(queue))
        tg.create_task(consumer(queue))

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
drains the queue. Memory stays bounded, and the system adapts to the
consumer's pace.

!!! warning

    Always set `maxsize`. Start with a small number (10--100) and adjust based
    on observation.

!!! tip "Trio users"

    [Trio][trio-docs]'s [`trio.open_memory_channel()`][trio-open-memory-channel] requires a max buffer
    size at creation time -- no "unbounded" default. asyncio's [`Queue`][queue] defaults
    to unbounded, which is why you must be disciplined about `maxsize`.

## Queue Shutdown Patterns

Eventually your producers run out of work and your consumers need to know it
is time to stop. The simplest approach is a *sentinel value* -- a special item
that means "no more data is coming." The most common sentinel is `#!py None`, but
any unique object works. The critical detail: **send one sentinel per
consumer.** If you have three consumers but only send one sentinel, two of
them will hang forever.

!!! tip

    If `#!py None` is a valid data value, define a dedicated sentinel:
    `#!py _STOP = object()`. Then compare with `#!py is _STOP` instead of `#!py is None`.

An alternative is [`task_done()`][task-done]/[`join()`][join]: the producer calls [`join()`][join] after
enqueuing all items, which blocks until every item has been marked done. This
tells you when all *work* is finished but does not tell consumers to stop.
Sentinels are simpler -- prefer them.

## Producer/Consumer with TaskGroup

Let's put everything together: multiple producers, multiple consumers, a
bounded queue, sentinel-based shutdown, and a [`TaskGroup`][taskgroup] managing it all.

The key design question is: who sends the sentinels? Individual producers
don't know when the others are done. The clean solution is a `run_producers`
function wrapping all producers in an inner [`TaskGroup`][taskgroup]. When that group
exits, the function sends the sentinels:

```python title="producer_consumer.py"
import asyncio
import random

SENTINEL: None = None

async def producer(
    name: str,
    queue: asyncio.Queue[tuple[str, int] | None],
    count: int,
) -> None:
    for i in range(count):
        await queue.put((name, i))
        await asyncio.sleep(random.uniform(0.01, 0.1))
    print(f"[{name}] finished producing {count} items")

async def consumer(
    name: str,
    queue: asyncio.Queue[tuple[str, int] | None],
) -> int:
    processed: int = 0
    while True:
        item: tuple[str, int] | None = await queue.get()
        if item is SENTINEL:
            queue.task_done()
            break
        source, seq = item
        await asyncio.sleep(0.05)  # Simulate work
        print(f"  [{name}] processed ({source}, {seq})")
        processed += 1
        queue.task_done()
    print(f"[{name}] shutting down after {processed} items")
    return processed

async def run_producers(
    queue: asyncio.Queue[tuple[str, int] | None],
    n_producers: int,
    items_each: int,
    n_consumers: int,
) -> None:
    async with asyncio.TaskGroup() as tg:
        for i in range(n_producers):
            tg.create_task(producer(f"P{i}", queue, items_each))
    # All producers are done -- send one sentinel per consumer
    for _ in range(n_consumers):
        await queue.put(SENTINEL)

async def main() -> None:
    n_producers: int = 2
    n_consumers: int = 3
    queue: asyncio.Queue[tuple[str, int] | None] = asyncio.Queue(maxsize=4)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(run_producers(queue, n_producers, 4, n_consumers))
        consumer_tasks = [
            tg.create_task(consumer(f"C{i}", queue))
            for i in range(n_consumers)
        ]

    total: int = sum(t.result() for t in consumer_tasks)
    print(f"\nTotal processed: {total}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python producer_consumer.py"
  [C0] processed (P0, 0)
  [C1] processed (P1, 0)
  [C2] processed (P0, 1)
  [C0] processed (P1, 1)
  [C1] processed (P0, 2)
  [C2] processed (P1, 2)
[P0] finished producing 4 items
  [C0] processed (P0, 3)
  [C1] processed (P1, 3)
[P1] finished producing 4 items
[C2] shutting down after 2 items
[C0] shutting down after 3 items
[C1] shutting down after 3 items

Total processed: 8
```

The inner [`TaskGroup`][taskgroup] ensures all producers finish before sentinels are sent.
Consumers run inside the outer group, draining the queue the whole time.

!!! warning

    If a producer raises, the inner [`TaskGroup`][taskgroup] cancels its siblings and the
    exception propagates to the outer group, which cancels the consumers. This
    is correct -- if producers fail, consumers should not wait for data that
    will never arrive.

## [`asyncio.Lock`][asyncio-lock]

When you *must* share mutable state between tasks, a
[`Lock`][lock]
serialises access. Only one task can hold the lock at a time; others suspend
until it is released. The idiomatic usage is [`async with`][async-with]:

```python title="lock_example.py"
import asyncio

async def transfer(
    lock: asyncio.Lock,
    ledger: dict[str, int],
    src: str,
    dst: str,
    amount: int,
) -> None:
    async with lock:
        if ledger[src] < amount:
            print(f"Insufficient funds in {src}")
            return
        await asyncio.sleep(0.01)  # Simulate async work between read and write
        ledger[src] -= amount
        ledger[dst] += amount
        print(f"Transferred {amount} from {src} to {dst}")

async def main() -> None:
    lock = asyncio.Lock()
    ledger: dict[str, int] = {"alice": 100, "bob": 50}

    async with asyncio.TaskGroup() as tg:
        tg.create_task(transfer(lock, ledger, "alice", "bob", 30))
        tg.create_task(transfer(lock, ledger, "alice", "bob", 30))
        tg.create_task(transfer(lock, ledger, "bob", "alice", 10))

    print(f"Final balances: {ledger}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python lock_example.py"
Transferred 30 from alice to bob
Transferred 30 from alice to bob
Transferred 10 from bob to alice
Final balances: {'alice': 50, 'bob': 60}
```

Without the lock, the [`await`][await] between reading and writing would create a race
condition -- two tasks could both see `#!py alice: 100` and each deduct 30.

!!! danger

    asyncio locks are **not reentrant**. If a task that already holds the lock
    tries to acquire it again, it will deadlock. If you need reentrant locking,
    see Chapter 2's advanced coordination section.

!!! tip

    Prefer queues over locks whenever possible. A queue makes data flow explicit
    and avoids bugs where you forget to acquire the lock or hold two locks in
    the wrong order.

## [`asyncio.Event`][asyncio-event]

An [`Event`][event]
is a simple flag that tasks can wait on. It starts unset.
[`event.set()`][event-set]
raises the flag, waking all tasks blocked on
[`event.wait()`][event-wait].
The event stays set until you call
[`event.clear()`][event-clear],
and you can check its state with
[`event.is_set()`][event-is-set].

The classic use case is startup coordination -- tasks that wait until a
service is ready:

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
        tg.create_task(database_init(db_ready))
        tg.create_task(request_handler("req-1", db_ready))
        tg.create_task(request_handler("req-2", db_ready))
        tg.create_task(request_handler("req-3", db_ready))

if __name__ == "__main__":
    asyncio.run(main())
```

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

All three handlers blocked on `#!py db_ready.wait()` until `#!py ready.set()` was
called, then woke up simultaneously. Calling `#!py wait()` *after* the event is
already set returns immediately -- no race condition.

!!! note

    An [`Event`][event] is best suited for *one-shot* or *phase-transition* signaling: a
    resource is ready, a shutdown has been requested, initialisation is complete.
    If you need repeated notifications, a [`Queue`][queue] or a [`Condition`][condition] (Chapter 2)
    is a better fit.

## [`asyncio.Semaphore`][asyncio-semaphore]

A [`Semaphore`][semaphore]
limits how many tasks can enter a section of code concurrently. Create one
with a count, and each `#!py async with semaphore:` decrements it. When it hits
zero, the next task suspends until someone exits.

The most common use case is limiting concurrency against an external
resource -- an API, a database connection pool, or a filesystem that chokes
under too many parallel reads:

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
        tasks = [tg.create_task(fetch_url(sem, url)) for url in urls]

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
active at any given time. This gives you the full concurrency of a [`TaskGroup`][taskgroup]
with a hard cap on how many tasks are doing real work simultaneously.

!!! tip "Trio users"

    [Trio][trio-docs] has [`trio.CapacityLimiter`][trio-capacity-limiter], which works similarly but
    has stricter ownership semantics. asyncio's [`Semaphore`][semaphore] is simpler -- it is
    just a counter.

!!! warning

    A [`Semaphore`][semaphore] limits concurrency, not rate. A semaphore with a value of 3
    means "at most 3 tasks at once," not "3 tasks per second." If you need rate
    limiting, you need a token bucket or leaky bucket algorithm.

## Choosing the Right Tool

When you need tasks to communicate, reach for a **Queue** -- it provides
natural backpressure and makes data flow explicit. When tasks must share
mutable state, use a **Lock** to serialise access. When one task needs to
signal others that a condition has been met, use an **Event**. When you want
to limit how many tasks are active at once, use a **Semaphore**. These four
cover the vast majority of coordination needs; for [`Condition`][condition], [`Barrier`][barrier],
and the bounded/priority queue variants, see
[Chapter 2](../beyond-the-basics/advanced-coordination.md).

---

[async-with]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[asyncio-event]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event
[asyncio-lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[asyncio-queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[asyncio-queue-maxsize]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[asyncio-semaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
[await]: https://docs.python.org/3/reference/expressions.html#await
[barrier]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier
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
