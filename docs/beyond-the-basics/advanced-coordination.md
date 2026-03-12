---
title: Advanced Coordination
description: >-
  A short guide to the specialized asyncio coordination primitives --
  Condition, Barrier, BoundedSemaphore, PriorityQueue, and LifoQueue -- with
  advice on when to use them and when to rely on the official docs.
---

# Advanced Coordination

The [Coordination](../the-basics/coordination.md) section in
[The Basics](../the-basics/index.md) covered the four coordination primitives
you will use most often -- Queue, Lock, Event, and Semaphore. Those handle the
vast majority of inter-task communication.

This section is about the *specialized* tools that you reach for when those four
are not enough. It is intentionally short. The official docs already document
these APIs well, so the goal here is to help you choose the right tool and avoid
the main footguns.

!!! Info

    Use this section for the decision-making. Use the official docs for the full
    method reference. The relevant stdlib pages are
    [Synchronization Primitives][sync-primitives] and [Queues][queues].

## Start With the Simpler Primitive

Before you reach for anything in this section, ask yourself:

- Would a bounded [`Queue`][queue] solve this more simply?
- Would a plain [`Event`][event] or [`Semaphore`][semaphore] be enough?
- Are you starting to rebuild a queue or a task group by hand?

If the answer to any of those is "yes", stop there. These advanced primitives
are useful, but they are easier to misuse.

## Decision Table

| Primitive | Reach for it when... | Main pitfall |
|---|---|---|
| [`Condition`][condition] | Several tasks wait for *different predicates* on the same shared state | Forgetting to re-check the predicate after wakeup |
| [`Barrier`][barrier] | A fixed number of tasks must all finish phase N before any start phase N+1 | One missing party stalls everyone |
| [`BoundedSemaphore`][boundedsemaphore] | You want semaphore behavior plus protection against over-release bugs | Treating it like a different concurrency primitive instead of a safety wrapper |
| [`PriorityQueue`][priorityqueue] | Work items must be processed by priority instead of FIFO order | Forgetting that ties still need stable, comparable payloads |
| [`LifoQueue`][lifoqueue] | Newest work should be processed first | Accidentally starving older items |

## `asyncio.Condition`

Use a [`Condition`][condition] when tasks share mutable state and different
waiters care about different states of that data.

You almost always want [`wait_for(predicate)`][wait-for-predicate] instead of raw [`wait()`][wait], because
it keeps the "check predicate, sleep, check again" loop in one place.

```python
import asyncio


class Buffer:
    def __init__(self) -> None:
        self.items: list[int] = []
        self.cond = asyncio.Condition()

    async def put(self, value: int) -> None:
        async with self.cond:
            self.items.append(value)
            self.cond.notify_all()

    async def get(self) -> int:
        async with self.cond:
            await self.cond.wait_for(lambda: bool(self.items))
            return self.items.pop(0)
```

If that looks like a hand-rolled queue, that is the point: prefer
[`Queue`][queue] unless you genuinely need a custom predicate over shared state.

## `asyncio.Barrier`

Use a [`Barrier`][barrier] for phased work. Each task calls [`await barrier.wait()`][await-barrier-wait].
Nobody crosses until the required number of parties arrives.

This is useful for simulations, staged pipelines, or test harnesses where all
workers must finish one round before the next begins.

The main failure mode is simple: if one task exits early, blocks forever, or is
never started, every other waiter can hang behind the barrier.

If the party count is not truly fixed, a barrier is probably the wrong tool.

## `asyncio.BoundedSemaphore`

[`BoundedSemaphore`][boundedsemaphore] is just a [`Semaphore`][semaphore] with one extra
safety check: [`release()`][release] raises if you call it more times than you acquired.

That makes it a debugging and correctness tool, not a fundamentally different
coordination pattern. Use it when an over-release would be a serious bug and you
want that bug to surface immediately.

## `PriorityQueue` and `LifoQueue`

These are queue variants, so the usual queue advice still applies:

- keep them bounded
- prefer sentinels for shutdown
- keep ownership inside a [`TaskGroup`][taskgroup]

Use [`PriorityQueue`][priorityqueue] when ordering matters more than arrival time:

```python
await queue.put((0, "urgent"))
await queue.put((10, "later"))
```

Use [`LifoQueue`][lifoqueue] when the newest item is the one you most want to
process next, for example when you care more about freshness than fairness.

Be aware that LIFO ordering can starve old items if new work keeps arriving.

## What to Read Next

- Full primitive behavior: [Synchronization Primitives][sync-primitives]
- Queue variants: [Queues][queues]
- The guide's first-line coordination advice:
  [Coordination](../the-basics/coordination.md)

[queue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
[event]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event
[semaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
[condition]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition
[barrier]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier
[boundedsemaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.BoundedSemaphore
[priorityqueue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.PriorityQueue
[lifoqueue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.LifoQueue
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[sync-primitives]: https://docs.python.org/3/library/asyncio-sync.html
[queues]: https://docs.python.org/3/library/asyncio-queue.html
[await-barrier-wait]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier.wait
[wait-for-predicate]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.wait_for
[release]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore.release
[wait]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.wait
