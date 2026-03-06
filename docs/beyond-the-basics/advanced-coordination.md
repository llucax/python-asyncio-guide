---
title: Advanced Coordination
description: >-
  Specialized asyncio coordination primitives — Condition, Barrier,
  BoundedSemaphore, PriorityQueue, and LifoQueue. Solve specific
  inter-task synchronization problems beyond Queue, Lock, Event,
  and Semaphore.
---

# Advanced Coordination

Chapter 1 covered the four coordination primitives you will use most often --
[Queue, Lock, Event, and Semaphore](../everyday-asyncio/coordination.md).
Those handle the vast majority of inter-task communication. This section
covers the *specialised* primitives -- tools you reach for less often, but
that solve specific problems cleanly when you do need them. Each one gets a
short explanation and a runnable example.

## `asyncio.Condition`

A [`Condition`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition)
combines a `Lock` with the ability to *wait for a condition to become true*.
The idea comes from threading: you acquire the lock, check whether the state
you care about is ready, and if it isn't, you call `wait()` -- which releases
the lock and suspends you until another task calls `notify()` or
`notify_all()`. When you wake up, the lock is re-acquired automatically.

This is useful when a simple `Event` isn't enough -- for example, when
multiple tasks are waiting for *different* conditions on the *same* shared
state.

The API:

- **`async with condition:`** -- acquires the underlying lock.
- **`await condition.wait()`** -- releases the lock, suspends until notified,
  then re-acquires the lock. **Always call this inside a `while` loop** that
  checks the actual condition -- spurious wakeups are possible, and another
  task may have changed the state before you re-acquire.
- **`await condition.wait_for(predicate)`** -- convenience wrapper that loops
  on `wait()` until `predicate()` returns `True`.
- **`condition.notify(n=1)`** -- wake up *n* waiting tasks.
- **`condition.notify_all()`** -- wake up *all* waiting tasks.

Here is a bounded buffer where producers wait when the buffer is full and
consumers wait when it is empty:

```python
# condition_buffer.py
import asyncio

class BoundedBuffer:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.buffer: list[int] = []
        self.condition = asyncio.Condition()

    async def put(self, item: int) -> None:
        async with self.condition:
            await self.condition.wait_for(lambda: len(self.buffer) < self.capacity)
            self.buffer.append(item)
            self.condition.notify_all()

    async def get(self) -> int:
        async with self.condition:
            await self.condition.wait_for(lambda: len(self.buffer) > 0)
            item = self.buffer.pop(0)
            self.condition.notify_all()
            return item

async def producer(buf: BoundedBuffer, name: str, count: int) -> None:
    for i in range(count):
        await buf.put(i)
        print(f"[{name}] put {i}")

async def consumer(buf: BoundedBuffer, name: str, count: int) -> None:
    for _ in range(count):
        item = await buf.get()
        await asyncio.sleep(0.1)  # Simulate processing
        print(f"[{name}] got {item}")

async def main() -> None:
    buf = BoundedBuffer(capacity=2)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(buf, "P", 5))
        tg.create_task(consumer(buf, "C1", 3))
        tg.create_task(consumer(buf, "C2", 2))

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python condition_buffer.py
[P] put 0
[P] put 1
[C1] got 0
[C2] got 1
[P] put 2
[P] put 3
[C1] got 2
[P] put 4
[C2] got 3
[C1] got 4
```

!!! note

    For simple producer/consumer scenarios, a
    [`Queue`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue)
    is usually the better choice -- it handles all the locking and
    notification internally. `Condition` shines when you need custom
    predicates on shared state that doesn't fit the queue model.

## `asyncio.Barrier`

A [`Barrier`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier)
is a synchronisation point where exactly *N* tasks must arrive before any of
them can continue. You create a barrier with a *parties* count, and each task
calls `await barrier.wait()`. The first *N - 1* callers suspend; the *N*-th
caller unblocks everyone.

!!! info

    `asyncio.Barrier` was added in **Python 3.11**. It is not available in
    earlier versions.

Barriers are ideal for *phased computations* -- situations where all workers
must complete phase 1 before any of them start phase 2.

```python
# barrier_phases.py
import asyncio

async def worker(name: str, barrier: asyncio.Barrier) -> None:
    for phase in range(1, 4):
        # Simulate work that takes different time for each worker
        work_time = 0.1 * (hash(name + str(phase)) % 3 + 1)
        await asyncio.sleep(work_time)
        print(f"[{name}] finished phase {phase}")

        await barrier.wait()
        # All workers have completed this phase before anyone continues
        print(f"[{name}] starting phase {phase + 1}")

async def main() -> None:
    n_workers = 3
    barrier = asyncio.Barrier(n_workers)

    async with asyncio.TaskGroup() as tg:
        for i in range(n_workers):
            tg.create_task(worker(f"W{i}", barrier))

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python barrier_phases.py
[W1] finished phase 1
[W0] finished phase 1
[W2] finished phase 1
[W2] starting phase 2
[W1] starting phase 2
[W0] starting phase 2
[W0] finished phase 2
[W2] finished phase 2
[W1] finished phase 2
[W1] starting phase 3
...
```

All workers complete each phase before any of them start the next. The
barrier resets automatically after each round, so you can reuse it across
multiple phases.

Other useful attributes and methods:
[`barrier.parties`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier.parties) (required count),
[`barrier.n_waiting`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier.n_waiting) (currently blocked),
[`await barrier.abort()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier.abort) (breaks the barrier -- all current and future `wait()` calls raise
[`BrokenBarrierError`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.BrokenBarrierError)),
and [`await barrier.reset()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier.reset) (returns to initial state; waiting tasks get `BrokenBarrierError`).

## `asyncio.BoundedSemaphore`

Chapter 1 covered
[`Semaphore`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore)
-- a counter that limits how many tasks can enter a section at once.
[`BoundedSemaphore`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.BoundedSemaphore)
works the same way with one extra safety check: if you `release()` more times
than you `acquire()`, it raises `ValueError` instead of silently incrementing
the counter past its initial value.

```python
# bounded_semaphore.py
import asyncio

async def main() -> None:
    sem = asyncio.BoundedSemaphore(2)

    await sem.acquire()
    await sem.acquire()
    print(f"Both slots acquired (value started at 2)")

    sem.release()
    sem.release()
    print("Released both -- back to 2")

    try:
        sem.release()  # Bug: one release too many
    except ValueError as exc:
        print(f"Caught: {exc}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python bounded_semaphore.py
Both slots acquired (value started at 2)
Released both -- back to 2
Caught: BoundedSemaphore released too many times
```

A regular `Semaphore` would have silently bumped the count to 3 in that last
`release()` call, allowing one more task than intended to enter the critical
section. With `BoundedSemaphore`, the bug surfaces immediately.

!!! tip

    Prefer `BoundedSemaphore` over `Semaphore` when the acquire/release
    calls happen in different places or different functions -- i.e., anywhere
    you are *not* using `async with`. The `async with` pattern makes extra
    releases impossible, so a plain `Semaphore` is fine there.

## `asyncio.PriorityQueue`

[`PriorityQueue`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.PriorityQueue)
is a subclass of `Queue` that delivers items lowest-value-first instead of
FIFO. Under the hood it uses a heap, so `put()` and `get()` are O(log n).

The catch: items must be comparable with `<`. If you put in objects that don't
support ordering, you will get a `TypeError`. The standard pattern is to use
tuples of `(priority, sequence_number, payload)` -- the sequence number
breaks ties so that items with equal priority come out in insertion order, and
the payload itself never needs to be compared:

```python
# priority_queue.py
import asyncio
from dataclasses import dataclass, field

@dataclass(order=False)
class Job:
    name: str
    data: str = field(repr=False, default="")

async def main() -> None:
    pq: asyncio.PriorityQueue[tuple[int, int, Job]] = (
        asyncio.PriorityQueue(maxsize=10)
    )

    # (priority, sequence, payload) -- lower priority number = higher urgency
    seq = 0
    for priority, name in [(3, "low-1"), (1, "critical"), (3, "low-2"), (2, "normal")]:
        await pq.put((priority, seq, Job(name)))
        seq += 1

    while not pq.empty():
        pri, _, job = await pq.get()
        print(f"  priority={pri}  job={job.name}")
        pq.task_done()

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python priority_queue.py
  priority=1  job=critical
  priority=2  job=normal
  priority=3  job=low-1
  priority=3  job=low-2
```

The `critical` job comes out first despite being inserted second. The two
priority-3 jobs come out in insertion order thanks to the sequence number.

!!! warning

    Without the sequence number, two items with the same priority would be
    compared by their payload. If the payload type doesn't implement
    `__lt__`, you get a `TypeError`. Always include a tie-breaker.

## `asyncio.LifoQueue`

[`LifoQueue`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.LifoQueue)
is a stack-like queue -- last in, first out. It shares the same API as `Queue`
(`put`, `get`, `maxsize`, `task_done`, `join`), but `get()` returns the *most
recently added* item.

This is useful when freshness matters more than fairness -- for example,
processing the most recent request first or implementing a work-stealing
scheduler:

```python
# lifo_queue.py
import asyncio

async def main() -> None:
    stack: asyncio.LifoQueue[str] = asyncio.LifoQueue(maxsize=5)

    for item in ["first", "second", "third"]:
        await stack.put(item)
        print(f"  pushed: {item}")

    print()
    while not stack.empty():
        item = await stack.get()
        print(f"  popped: {item}")
        stack.task_done()

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python lifo_queue.py
  pushed: first
  pushed: second
  pushed: third

  popped: third
  popped: second
  popped: first
```

Items come out in reverse insertion order -- classic stack behaviour.

## Choosing Between Queue Variants

All three queue types share the same interface (`put`, `get`, `maxsize`,
`task_done`, `join`). They differ only in the order items come out:

| Class | Order | Use when... |
|---|---|---|
| [`Queue`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue) | FIFO (first in, first out) | You want fair, predictable ordering. The default choice. |
| [`LifoQueue`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.LifoQueue) | LIFO (last in, first out) | Freshness matters more than fairness -- process the newest item first. |
| [`PriorityQueue`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.PriorityQueue) | Lowest value first | Items have explicit priorities. Use `(priority, seq, payload)` tuples. |

!!! tip

    Start with `Queue`. Switch to `PriorityQueue` or `LifoQueue` only when
    you have a concrete reason -- priority-based scheduling, freshness
    requirements, or stack-like semantics. All three support `maxsize` for
    backpressure.

---
