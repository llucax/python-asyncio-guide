---
title: Advanced Coordination
description: >-
  A short guide to the less-common asyncio coordination tools -- Lock,
  Condition, Barrier, queue completion tracking, BoundedSemaphore, and
  specialty queues -- with advice on when to use them and when to rely on the
  official docs.
---

# Advanced Coordination

The [Coordination](../the-basics/coordination.md) section in
[The Basics](../the-basics/index.md) covered the coordination tools you will
reach for first -- [`Queue`][queue], [`Event`][event], and
[`Semaphore`][semaphore].

This section picks up where that leaves off. These tools are not "expert-only";
they are just less common in straightforward asyncio programs. You reach for
them when message passing is not enough, when shared mutable state is
unavoidable, or when you need a more specialized coordination pattern.

That includes [`Lock`][lock], [`Condition`][condition], [`Barrier`][barrier],
one queue-specific pattern -- [`task_done()`][task-done] and [`join()`][join]
-- plus [`BoundedSemaphore`][boundedsemaphore], [`PriorityQueue`][priorityqueue],
and [`LifoQueue`][lifoqueue]. It is intentionally short. The official docs
already document these APIs well, so the goal here is to help you choose the
right tool and avoid the main footguns.

!!! Info

    Use this section for the decision-making. Use the official docs for the full
    method reference. The relevant stdlib pages are
    [Synchronization Primitives][sync-primitives] and [Queues][queues].

## Start With the Simpler Primitive

Before you reach for anything in this section, ask yourself:

- Could one task own this state and expose a bounded [`Queue`][queue]
  interface instead?
- Would a plain [`Event`][event] or [`Semaphore`][semaphore] be enough?
- Are you starting to rebuild a queue or a task group by hand?

If the answer to any of those is "yes", stop there. These tools are useful,
but they are easier to misuse.

## Decision Table

| Tool | Reach for it when... | Main pitfall |
|---|---|---|
| [`Lock`][lock] | Several tasks must preserve one shared-state invariant across an [`await`][await] | Holding it across unrelated slow work, or reaching for it when a queue would be simpler |
| [`Condition`][condition] | Several tasks wait for *different predicates* on the same shared state | Forgetting to re-check the predicate after wakeup |
| [`Barrier`][barrier] | A fixed number of tasks must all finish phase N before any start phase N+1 | One missing party stalls everyone |
| [`Queue.task_done()`][task-done] and [`Queue.join()`][join] | You need to wait for queued work to drain without tearing down the worker tasks | Mistaking it for a shutdown signal or a true barrier |
| [`BoundedSemaphore`][boundedsemaphore] | You want semaphore behavior plus protection against over-release bugs | Treating it like a different concurrency primitive instead of a safety wrapper |
| [`PriorityQueue`][priorityqueue] | Work items must be processed by priority instead of FIFO order | Forgetting that ties still need stable, comparable payloads |
| [`LifoQueue`][lifoqueue] | Newest work should be processed first | Accidentally starving older items |

## `asyncio.Lock`

Use a [`Lock`][lock] when tasks really do share mutable state directly and one
invariant has to survive across an [`await`][await].

In threaded code, locks are routine because another thread can interrupt you at
any point. asyncio is different: tasks are cooperative, so straight-line code
already runs to completion relative to other tasks until it hits an
[`await`][await]. That is why locks are more of an escape hatch than a default
pattern in async code.

A lock starts to make sense when both of these are true:

- multiple tasks touch the same mutable object directly
- correctness depends on a state transition that spans an [`await`][await]

If one task can own the state and other tasks can talk to it through a
[`Queue`][queue], prefer that design. When you do need a lock, use
[`async with`][async-with] so release is guaranteed:

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

        await asyncio.sleep(0.01)  # Simulate writing a pending-transfer audit record
        ledger[src] -= amount
        ledger[dst] += amount
        print(f"Transferred {amount} from {src} to {dst}")


async def main() -> None:
    lock = asyncio.Lock()
    ledger: dict[str, int] = {"alice": 100, "bob": 50}

    async with asyncio.TaskGroup() as tg:
        tg.create_task(
            transfer(lock, ledger, "alice", "bob", 80),
            name="alice-to-bob-1",
        )
        tg.create_task(
            transfer(lock, ledger, "alice", "bob", 80),
            name="alice-to-bob-2",
        )

    print(f"Final balances: {ledger}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python lock_example.py"
Transferred 80 from alice to bob
Insufficient funds in alice
Final balances: {'alice': 20, 'bob': 130}
```

The `#!py await asyncio.sleep(0.01)` stands in for real async work that is part
of the same invariant -- for example, recording a pending transfer before the
balance change is committed. Without the lock, both tasks could read `#!py
alice: 100`, both pass the insufficient-funds check, then both resume later
and deduct 80. The result would be an impossible negative balance.

If there were no [`await`][await] between the balance check and the updates,
another task could not cut into that straight-line block. That is why locks are
much less common in asyncio than they are in threaded programs.

!!! Note

    Keep the locked region as small as you can. If some awaited work is not
    part of the invariant, move it outside the lock. In this example the
    simulated audit write stays inside because the transfer is not considered
    committed until that write succeeds.

!!! Danger

    asyncio locks are **not reentrant**. If a task that already holds the lock
    tries to acquire it again, it will deadlock.

!!! Tip

    Prefer queues or single-task ownership over locks whenever possible. In
    asyncio, those designs usually fit the cooperative model better: one task
    owns the state, and other tasks send it work.

## `asyncio.Condition`

[`Condition`][condition] combines the shared-state pattern of a [`Lock`][lock]
with wait/notify coordination. Use it when tasks share mutable state and
different waiters care about different states of that data.

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

If you need to wait for queued work to drain instead of waiting for a fixed set
of tasks to rendezvous, see [Queue Completion
Tracking](#queue-completion-tracking).

## Queue Completion Tracking

[`Queue.task_done()`][task-done] and [`Queue.join()`][join] are not a separate
primitive. They are completion tracking built into [`Queue`][queue]. They can
feel a little like a barrier, but the mental model is different: a
[`Barrier`][barrier] counts tasks reaching a rendezvous point, while
[`join()`][join] counts unfinished queue items.

Each [`put(item)`][put-item] increments the unfinished-work counter. After a
consumer fully processes an item, it calls [`task_done()`][task-done] to
decrement it. [`join()`][join] blocks until the counter reaches zero.

In structured-concurrency code, you often do not need this. If the producer,
consumers, and coordinator all live inside the same [`TaskGroup`][taskgroup],
the group already answers "when is the whole pipeline done?" Reach for
[`join()`][join] only when you need an earlier checkpoint inside that scope:
drain the current batch, flush outstanding work before shutdown, or let workers
catch up while keeping them alive.

```python title="queue_join_batches.py"
import asyncio

STOP: None = None


async def worker(name: str, queue: asyncio.Queue[int | None]) -> None:
    while True:
        item: int | None = await queue.get()
        if item is STOP:
            queue.task_done()
            print(f"{name}: stopping")
            return

        await asyncio.sleep(0.2)
        print(f"{name}: processed {item}")
        queue.task_done()


async def submit(
    queue: asyncio.Queue[int | None],
    items: list[int],
) -> None:
    for item in items:
        await queue.put(item)


async def main() -> None:
    queue: asyncio.Queue[int | None] = asyncio.Queue(maxsize=3)
    n_workers: int = 2

    async with asyncio.TaskGroup() as tg:
        for i in range(n_workers):
            tg.create_task(worker(f"W{i}", queue), name=f"worker-{i}")

        await submit(queue, [1, 2, 3, 4])
        await queue.join()
        print("First batch drained")

        await submit(queue, [5, 6])
        await queue.join()
        print("Second batch drained")

        for _ in range(n_workers):
            await queue.put(STOP)


if __name__ == "__main__":
    asyncio.run(main())
```

The workers stay alive across both batches. [`join()`][join] gives `#!py
main()` an intermediate "all work so far is done" checkpoint without tearing
down the worker tasks. The sentinels still handle shutdown, and because they
are queue items too, each worker calls [`task_done()`][task-done] before
exiting.

!!! Warning

    Call [`task_done()`][task-done] exactly once for each item returned by
    [`get()`][get]. Too few calls make [`join()`][join] wait forever; too many
    raise `ValueError`.

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
[lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[condition]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition
[barrier]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier
[boundedsemaphore]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.BoundedSemaphore
[priorityqueue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.PriorityQueue
[lifoqueue]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.LifoQueue
[get]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get
[join]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.join
[put-item]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put
[task-done]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[sync-primitives]: https://docs.python.org/3/library/asyncio-sync.html
[queues]: https://docs.python.org/3/library/asyncio-queue.html
[async-with]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[await]: https://docs.python.org/3/reference/expressions.html#await
[await-barrier-wait]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier.wait
[wait-for-predicate]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.wait_for
[release]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore.release
[wait]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.wait
