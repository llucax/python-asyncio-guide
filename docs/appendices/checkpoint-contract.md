# Checkpoint Contract

Every `await` expression is a *potential* checkpoint -- a point where the
current task may suspend and let another task run. But "potential" is the key
word. Some `await`s always suspend. Some only suspend when a certain condition
holds. And many asyncio operations are not `await`able at all -- they are plain
synchronous calls that never yield control. Knowing which category an operation
falls into is essential for reasoning about task interleaving, cancellation
delivery, and starvation. [Debugging](../everyday-asyncio/debugging.md)
introduced a condensed three-row version of this table; what follows is the
full reference.

The rules below apply to **Python 3.11+** and cover the modern asyncio API
surface. Deprecated APIs (`gather()`, `ensure_future()`, `get_event_loop()`,
etc.) are intentionally omitted.

### How to read the tables

Each operation is placed in exactly one of three categories:

- **Always suspends** -- the operation yields control to the event loop every
  time, unconditionally. Other tasks *will* get a chance to run.
- **Conditionally suspends** -- the operation is a coroutine that you `await`,
  but it may or may not actually yield. The table lists the conditions that
  determine which path is taken.
- **Never suspends** -- the operation is synchronous. No `await` is involved,
  and no other task can interleave.

Operations that appear in both the "always" and "conditionally" tables (like
`Lock.acquire()` or `Queue.get()`) are listed in both places with their
respective conditions, so you can look up any operation and immediately see the
full picture.

---

## Always Suspends

These operations yield to the event loop every time they are awaited,
regardless of the current state. Another task is guaranteed an opportunity to
run.

| Operation | Notes |
|-----------|-------|
| [`asyncio.sleep(delay)`](https://docs.python.org/3/library/asyncio-task.html#asyncio.sleep) | Always suspends, even when `delay=0`. `sleep(0)` is the canonical way to insert an explicit checkpoint. |
| [`stream.read(n)`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.read) | Waits for up to `n` bytes from the stream. |
| [`stream.readline()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readline) | Waits for a complete line (up to the separator). |
| [`stream.readexactly(n)`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readexactly) | Waits until exactly `n` bytes have been received. Raises [`IncompleteReadError`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.IncompleteReadError) if EOF arrives first. |
| [`stream.readuntil(separator)`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readuntil) | Waits until the separator is found in the buffer. |
| [`Queue.get()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get) on an empty queue | Suspends until a producer calls `put()` or `put_nowait()`. |
| [`Queue.put(item)`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put) on a full queue | Suspends until a consumer calls `get()` or `get_nowait()`. |
| [`Queue.join()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.join) | Suspends until every item has been marked done via [`task_done()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done). |
| [`Lock.acquire()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock.acquire) when the lock is held | Suspends until the holder calls `release()`. |
| [`Event.wait()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.wait) when the event is not set | Suspends until another task calls `set()`. |
| [`Condition.wait()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.wait) | Releases the underlying lock, suspends until notified, then re-acquires the lock. Always suspends at least once. |
| [`Condition.wait_for(predicate)`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.wait_for) | Repeatedly calls `wait()` until `predicate()` returns `True`. Suspends at least once even if the predicate is already true on the first check. |
| [`Semaphore.acquire()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore.acquire) when the internal counter is 0 | Suspends until another task calls `release()`. |
| [`Barrier.wait()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier.wait) | Suspends until the required number of tasks have called `wait()`. |
| [`asyncio.wait()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait) | Suspends until at least one task matches the `return_when` condition. |
| [`asyncio.wait_for(aw, timeout)`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for) | Suspends until the awaitable completes or the timeout expires. |

---

## Conditionally Suspends

These operations are coroutines (you `await` them), but whether they actually
yield to the event loop depends on runtime state. If the fast-path condition is
met, they return immediately *without* giving other tasks a turn. This makes
them unreliable as cancellation checkpoints -- you cannot assume that an
`await` on one of these operations will give pending `CancelledError`s a chance
to land.

| Operation | Suspends when... | Returns immediately when... |
|-----------|------------------|-----------------------------|
| [`Lock.acquire()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock.acquire) | The lock is held by another task | The lock is free |
| [`Queue.get()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get) | The queue is empty | The queue has at least one item |
| [`Queue.put(item)`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put) | The queue is full | The queue has space (or is unbounded) |
| [`Event.wait()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.wait) | The event is not set | The event is already set |
| [`Semaphore.acquire()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore.acquire) | The internal counter is 0 | The counter is greater than 0 |
| [`stream.drain()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.drain) | The write buffer is above the high-water mark | The buffer is below the high-water mark |
| `await task` | The task is still running | The task is already done -- returns its result (or raises) immediately |
| `await future` | The future is not yet resolved | The future already has a result or exception |

> [!WARNING]
> **`await task` on an already-finished task does not suspend.** This is a
> common source of confusion. If you are counting on `await` as a checkpoint
> for cancellation delivery, and the awaitable has already completed, the
> cancellation check never happens. Insert an explicit `await asyncio.sleep(0)`
> when you need a guaranteed checkpoint.

Note that `stream.drain()` is particularly subtle. A common pattern is to call
`stream.write(data)` followed by `await stream.drain()`. Because `write()` is
synchronous and `drain()` only suspends when the buffer is full, a sequence of
small writes may execute entirely without yielding. If you need a checkpoint
between writes, add an explicit `await asyncio.sleep(0)`.

---

## Never Suspends

These are plain synchronous calls. They do not involve `await`, and the event
loop does not get a chance to run other tasks during their execution.

### Streams

| Operation | Notes |
|-----------|-------|
| [`stream.write(data)`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.write) | Buffers data for sending. Does not wait for the data to reach the peer -- follow up with [`drain()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.drain) to apply back-pressure. |
| [`stream.write_eof()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.write_eof) | Signals end-of-stream. Synchronous, like `write()`. |
| [`stream.close()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.close) | Initiates closing the stream. The close itself is synchronous; use [`wait_closed()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.wait_closed) to wait for it to finish. |

### Queues

| Operation | Notes |
|-----------|-------|
| [`Queue.put_nowait(item)`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put_nowait) | Raises [`QueueFull`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueFull) if no space is available. |
| [`Queue.get_nowait()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get_nowait) | Raises [`QueueEmpty`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueEmpty) if nothing is available. |
| [`Queue.qsize()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.qsize) / [`Queue.empty()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.empty) / [`Queue.full()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.full) | Queue size inspection. These are snapshots -- the value may be stale by the time you act on it. |
| [`Queue.task_done()`](https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done) | Marks a previously retrieved item as processed. |

### Synchronization primitives

| Operation | Notes |
|-----------|-------|
| [`Event.set()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.set) | Wakes all waiters, but does not yield. |
| [`Event.clear()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.clear) | Resets the event's internal flag. |
| [`Event.is_set()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.is_set) | Returns the current flag value. |
| [`Lock.release()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock.release) | Releases the lock. Wakes the next waiter, but does not yield. |
| [`Lock.locked()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock.locked) | Returns whether the lock is currently held. |
| [`Condition.notify()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.notify) / [`notify_all()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.notify_all) | Wakes waiters but does not yield. |
| [`Semaphore.release()`](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore.release) | Increments the counter and wakes a waiter if one is waiting. |

### Tasks and futures

| Operation | Notes |
|-----------|-------|
| [`task.cancel(msg=...)`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel) | *Requests* cancellation but returns immediately. The `CancelledError` is raised inside the target task at its next checkpoint. |
| [`task.done()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.done) | Returns `True` if the task has finished (successfully, with an exception, or by cancellation). |
| [`task.result()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.result) | Returns the result synchronously. Raises `InvalidStateError` if the task is not done. |
| [`task.exception()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.exception) | Returns the exception synchronously. Raises `InvalidStateError` if the task is not done. |
| [`task.cancelled()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancelled) | Returns whether the task was cancelled. |
| [`task.get_name()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.get_name) / [`task.set_name()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.set_name) | Name accessors. |
| [`future.set_result()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_result) / [`future.set_exception()`](https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_exception) | Resolves a future. Wakes awaiters at the next loop iteration, but the call itself is synchronous. |

---

## Implications

Three practical consequences follow from this table.

### Cancellation delivery requires a real checkpoint

[`task.cancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel)
does not raise `CancelledError` immediately -- it schedules the exception for
the next time the target task suspends at a checkpoint. If the task enters a
long stretch of synchronous code, or only `await`s things that resolve
immediately (the "conditionally suspends" rows in their fast-path state),
cancellation stays pending indefinitely. This is why
[`asyncio.timeout()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout)
can appear to not work: the deadline fires, `cancel()` is called, but the task
never reaches a checkpoint where the `CancelledError` can be delivered. The fix
is to ensure long-running code periodically hits a real checkpoint --
`await asyncio.sleep(0)` is the standard idiom.

### Starvation is caused by missing checkpoints

The asyncio event loop is cooperative: a task runs until it voluntarily
suspends. If a task loops over operations that never suspend (or only
conditionally suspend and the fast path keeps winning), no other task gets a
turn. This makes the program *appear* single-threaded and can cause timeouts
and watchdogs to fire late or not at all. The cure is the same: sprinkle
`await asyncio.sleep(0)` at regular intervals in CPU-bound or tight loops.
Better yet, offload heavy computation to a thread with
[`asyncio.to_thread()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread)
so the event loop stays responsive.

### Shared state is safe between checkpoints

On the flip side, the checkpoint contract gives you a strong guarantee:
between two consecutive checkpoints, no other task can run. This means you do
not need a lock to protect a read-modify-write sequence *as long as there is no
`await` (or only non-suspending `await`s) between the read and the write*.
Understanding exactly which operations suspend is what lets you distinguish the
safe cases from the unsafe ones -- and that is the purpose of this table.
