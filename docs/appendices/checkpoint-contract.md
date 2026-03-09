---
title: Checkpoint Contract
description: >-
  Complete reference for which asyncio operations always suspend,
  conditionally suspend, or never suspend. Essential for reasoning about
  task interleaving, cancellation delivery, and starvation.
---

# Checkpoint Contract

Every [`await`][await] expression is a *potential* checkpoint -- a point where the
current task may suspend and let another task run. But "potential" is the key
word. Some [`await`][await]s always suspend. Some only suspend when a certain condition
holds. And many asyncio operations are not [`await`][await]able at all -- they are plain
synchronous calls that never yield control. Knowing which category an operation
falls into is essential for reasoning about task interleaving, cancellation
delivery, and starvation. [Debugging](../the-basics/debugging.md)
introduced a condensed three-row version of this table; what follows is the
full reference.

The rules below apply to **Python 3.11+** and cover the modern asyncio API
surface. Deprecated APIs (`gather()`, `ensure_future()`, `get_event_loop()`,
etc.) are intentionally omitted.

### How to read the tables

Each operation is placed in exactly one of three categories:

- **Always suspends** -- the operation yields control to the event loop every
  time, unconditionally. Other tasks *will* get a chance to run.
- **Conditionally suspends** -- the operation is a coroutine that you [`await`][await],
  but it may or may not actually yield. The table lists the conditions that
  determine which path is taken.
- **Never suspends** -- the operation is synchronous. No [`await`][await] is involved,
  and no other task can interleave.

Operations that appear in both the "always" and "conditionally" tables (like
[`Lock.acquire()`][lock-acquire] or [`Queue.get()`][queue-get]) are listed in both places with their
respective conditions, so you can look up any operation and immediately see the
full picture.

---

## Always Suspends

These operations yield to the event loop every time they are awaited,
regardless of the current state. Another task is guaranteed an opportunity to
run.

| Operation | Notes |
|-----------|-------|
| [`asyncio.sleep(delay)`][asyncio-sleep-delay] | Always suspends, even when `delay=0`. `sleep(0)` is the canonical way to insert an explicit checkpoint. |
| [`stream.read(n)`][stream-read-n] | Waits for up to `n` bytes from the stream. |
| [`stream.readline()`][stream-readline] | Waits for a complete line (up to the separator). |
| [`stream.readexactly(n)`][stream-readexactly-n] | Waits until exactly `n` bytes have been received. Raises [`IncompleteReadError`][incompletereaderror] if EOF arrives first. |
| [`stream.readuntil(separator)`][stream-readuntil-separator] | Waits until the separator is found in the buffer. |
| [`Queue.get()`][queue-get] on an empty queue | Suspends until a producer calls `put()` or `put_nowait()`. |
| [`Queue.put(item)`][queue-put-item] on a full queue | Suspends until a consumer calls [`get()`][get] or [`get_nowait()`][get-nowait]. |
| [`Queue.join()`][queue-join] | Suspends until every item has been marked done via [`task_done()`][task-done]. |
| [`Lock.acquire()`][lock-acquire] when the lock is held | Suspends until the holder calls `release()`. |
| [`Event.wait()`][event-wait] when the event is not set | Suspends until another task calls `set()`. |
| [`Condition.wait()`][condition-wait] | Releases the underlying lock, suspends until notified, then re-acquires the lock. Always suspends at least once. |
| [`Condition.wait_for(predicate)`][condition-wait-for-predicate] | Repeatedly calls `wait()` until `predicate()` returns `True`. Suspends at least once even if the predicate is already true on the first check. |
| [`Semaphore.acquire()`][semaphore-acquire] when the internal counter is 0 | Suspends until another task calls `release()`. |
| [`Barrier.wait()`][barrier-wait] | Suspends until the required number of tasks have called `wait()`. |
| [`asyncio.wait()`][asyncio-wait] | Suspends until at least one task matches the `return_when` condition. |
| [`asyncio.wait_for(aw, timeout)`][asyncio-wait-for-aw-timeout] | Suspends until the awaitable completes or the timeout expires. |

---

## Conditionally Suspends

These operations are coroutines (you [`await`][await] them), but whether they actually
yield to the event loop depends on runtime state. If the fast-path condition is
met, they return immediately *without* giving other tasks a turn. This makes
them unreliable as cancellation checkpoints -- you cannot assume that an
[`await`][await] on one of these operations will give pending [`CancelledError`][cancellederror]s a chance
to land.

| Operation | Suspends when... | Returns immediately when... |
|-----------|------------------|-----------------------------|
| [`Lock.acquire()`][lock-acquire] | The lock is held by another task | The lock is free |
| [`Queue.get()`][queue-get] | The queue is empty | The queue has at least one item |
| [`Queue.put(item)`][queue-put-item] | The queue is full | The queue has space (or is unbounded) |
| [`Event.wait()`][event-wait] | The event is not set | The event is already set |
| [`Semaphore.acquire()`][semaphore-acquire] | The internal counter is 0 | The counter is greater than 0 |
| [`stream.drain()`][stream-drain] | The write buffer is above the high-water mark | The buffer is below the high-water mark |
| `await task` | The task is still running | The task is already done -- returns its result (or raises) immediately |
| `await future` | The future is not yet resolved | The future already has a result or exception |

!!! warning

    **`await task` on an already-finished task does not suspend.** This is
    a common source of confusion. If you are counting on [`await`][await] as a
    checkpoint for cancellation delivery, and the awaitable has already
    completed, the cancellation check never happens. Insert an explicit
    `await asyncio.sleep(0)` when you need a guaranteed checkpoint.

Note that [`stream.drain()`][stream-drain] is particularly subtle. A common pattern is to call
[`stream.write(data)`][stream-write-data] followed by `await stream.drain()`. Because `write()` is
synchronous and [`drain()`][drain] only suspends when the buffer is full, a sequence of
small writes may execute entirely without yielding. If you need a checkpoint
between writes, add an explicit `await asyncio.sleep(0)`.

---

## Never Suspends

These are plain synchronous calls. They do not involve [`await`][await], and the event
loop does not get a chance to run other tasks during their execution.

### Streams

| Operation | Notes |
|-----------|-------|
| [`stream.write(data)`][stream-write-data] | Buffers data for sending. Does not wait for the data to reach the peer -- follow up with [`drain()`][drain] to apply back-pressure. |
| [`stream.write_eof()`][stream-write-eof] | Signals end-of-stream. Synchronous, like `write()`. |
| [`stream.close()`][stream-close] | Initiates closing the stream. The close itself is synchronous; use [`wait_closed()`][wait-closed] to wait for it to finish. |

### Queues

| Operation | Notes |
|-----------|-------|
| [`Queue.put_nowait(item)`][queue-put-nowait-item] | Raises [`QueueFull`][queuefull] if no space is available. |
| [`Queue.get_nowait()`][queue-get-nowait] | Raises [`QueueEmpty`][queueempty] if nothing is available. |
| [`Queue.qsize()`][queue-qsize] / [`Queue.empty()`][queue-empty] / [`Queue.full()`][queue-full] | Queue size inspection. These are snapshots -- the value may be stale by the time you act on it. |
| [`Queue.task_done()`][queue-task-done] | Marks a previously retrieved item as processed. |

### Synchronization primitives

| Operation | Notes |
|-----------|-------|
| [`Event.set()`][event-set] | Wakes all waiters, but does not yield. |
| [`Event.clear()`][event-clear] | Resets the event's internal flag. |
| [`Event.is_set()`][event-is-set] | Returns the current flag value. |
| [`Lock.release()`][lock-release] | Releases the lock. Wakes the next waiter, but does not yield. |
| [`Lock.locked()`][lock-locked] | Returns whether the lock is currently held. |
| [`Condition.notify()`][condition-notify] / [`notify_all()`][notify-all] | Wakes waiters but does not yield. |
| [`Semaphore.release()`][semaphore-release] | Increments the counter and wakes a waiter if one is waiting. |

### Tasks and futures

| Operation | Notes |
|-----------|-------|
| [`task.cancel(msg=...)`][task-cancel-msg] | *Requests* cancellation but returns immediately. The [`CancelledError`][cancellederror] is raised inside the target task at its next checkpoint. |
| [`task.done()`][task-done-2] | Returns `True` if the task has finished (successfully, with an exception, or by cancellation). |
| [`task.result()`][task-result] | Returns the result synchronously. Raises `InvalidStateError` if the task is not done. |
| [`task.exception()`][task-exception] | Returns the exception synchronously. Raises `InvalidStateError` if the task is not done. |
| [`task.cancelled()`][task-cancelled] | Returns whether the task was cancelled. |
| [`task.get_name()`][task-get-name] / [`task.set_name()`][task-set-name] | Name accessors. |
| [`future.set_result()`][future-set-result] / [`future.set_exception()`][future-set-exception] | Resolves a future. Wakes awaiters at the next loop iteration, but the call itself is synchronous. |

---

## Implications

Three practical consequences follow from this table.

### Cancellation delivery requires a real checkpoint

[`task.cancel()`][task-cancel]
does not raise [`CancelledError`][cancellederror] immediately -- it schedules the exception for
the next time the target task suspends at a checkpoint. If the task enters a
long stretch of synchronous code, or only [`await`][await]s things that resolve
immediately (the "conditionally suspends" rows in their fast-path state),
cancellation stays pending indefinitely. This is why
[`asyncio.timeout()`][asyncio-timeout]
can appear to not work: the deadline fires, `cancel()` is called, but the task
never reaches a checkpoint where the [`CancelledError`][cancellederror] can be delivered. The fix
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
[`asyncio.to_thread()`][asyncio-to-thread]
so the event loop stays responsive.

### Shared state is safe between checkpoints

On the flip side, the checkpoint contract gives you a strong guarantee:
between two consecutive checkpoints, no other task can run. This means you do
not need a lock to protect a read-modify-write sequence *as long as there is no
[`await`][await] (or only non-suspending [`await`][await]s) between the read and the write*.
Understanding exactly which operations suspend is what lets you distinguish the
safe cases from the unsafe ones -- and that is the purpose of this table.

[await]: https://docs.python.org/3/reference/expressions.html#await
[lock-acquire]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock.acquire
[queue-get]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get
[asyncio-sleep-delay]: https://docs.python.org/3/library/asyncio-task.html#asyncio.sleep
[stream-read-n]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.read
[stream-readline]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readline
[stream-readexactly-n]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readexactly
[incompletereaderror]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.IncompleteReadError
[stream-readuntil-separator]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readuntil
[queue-put-item]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put
[get]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get
[get-nowait]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get_nowait
[queue-join]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.join
[task-done]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done
[event-wait]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.wait
[condition-wait]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.wait
[condition-wait-for-predicate]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.wait_for
[semaphore-acquire]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore.acquire
[barrier-wait]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Barrier.wait
[asyncio-wait]: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait
[asyncio-wait-for-aw-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[stream-drain]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.drain
[stream-write-data]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.write
[drain]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.drain
[stream-write-eof]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.write_eof
[stream-close]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.close
[wait-closed]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.wait_closed
[queue-put-nowait-item]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.put_nowait
[queuefull]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueFull
[queue-get-nowait]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.get_nowait
[queueempty]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.QueueEmpty
[queue-qsize]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.qsize
[queue-empty]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.empty
[queue-full]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.full
[queue-task-done]: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue.task_done
[event-set]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.set
[event-clear]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.clear
[event-is-set]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Event.is_set
[lock-release]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock.release
[lock-locked]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock.locked
[condition-notify]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.notify
[notify-all]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Condition.notify_all
[semaphore-release]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore.release
[task-cancel-msg]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel
[task-done-2]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.done
[task-result]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.result
[task-exception]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.exception
[task-cancelled]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancelled
[task-get-name]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.get_name
[task-set-name]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.set_name
[future-set-result]: https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_result
[future-set-exception]: https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_exception
[task-cancel]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[asyncio-to-thread]: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread