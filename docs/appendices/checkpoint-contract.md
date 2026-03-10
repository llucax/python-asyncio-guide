---
title: Checkpoint Contract
description: >-
  Guide-level reference for common asyncio operations and whether they
  suspend in CPython 3.11. Useful for reasoning about interleaving,
  cancellation delivery, and starvation, but not an official contract.
---

# Checkpoint Contract

!!! warning

    This appendix was collected on March 2026 against **CPython 3.11**. It is
    **not** an official asyncio contract, it is **not** guaranteed, and it may
    change at any time. Unless a row is marked **Official**, treat it as
    guide-level guidance only, and with care, derived from the Python docs plus
    a read of the CPython 3.11 source.

Every [`await`][await] expression is a *potential* checkpoint -- a point where the
current task may suspend and let another task run. But "potential" is the key
word. Some [`await`][await]s always suspend. Some only suspend when a certain
condition holds. And many asyncio operations are not [`await`][await]able at
all -- they are plain synchronous calls that never yield control.

Asyncio does not publish a single official checkpoint contract for the whole
API surface. This page is a practical reference for the common operations used
throughout this guide. Only rows marked **Official** are explicitly documented
by Python as always suspending the current task. Everything else here is an
interpretation of the docs and CPython 3.11's implementation details.

This appendix is intentionally not exhaustive. It omits many lower-level APIs
and less common awaitables. Use it as a mental-model guide, not as a language
guarantee.

### How to read the tables

Each operation is placed in exactly one of three categories:

- **Always suspends** -- the operation yields control to the event loop every
  time, unconditionally. Other tasks *will* get a chance to run.
- **Conditionally suspends** -- the operation is a coroutine that you [`await`][await],
  but it may or may not actually yield. The table lists the conditions that
  determine which path is taken.
- **Never suspends** -- the operation is synchronous. No [`await`][await] is involved,
  and no other task can interleave.

---

## Always Suspends

These operations yield to the event loop every time they are awaited,
regardless of the current state. Another task is guaranteed an opportunity to
run.

| Operation | Basis | Notes |
|-----------|-------|-------|
| [`asyncio.sleep(delay)`][asyncio-sleep-delay] | **Official** | The docs explicitly say `#!py sleep()` always suspends the current task, even when `delay=0`. `#!py sleep(0)` is the canonical explicit checkpoint. |
| [`Condition.wait()`][condition-wait] | Docs + source | It always releases the lock, waits to be notified, then re-acquires the lock. There is no fast path. |
| [`asyncio.wait()`][asyncio-wait] | CPython 3.11 source | In CPython 3.11, `#!py wait()` always awaits an internal waiter future before returning, even if every input future is already done. This is not an explicit docs guarantee. |

---

## Conditionally Suspends

These operations are coroutines (you [`await`][await] them), but whether they actually
yield to the event loop depends on runtime state. If the fast-path condition is
met, they return immediately *without* giving other tasks a turn. This makes
them unreliable as cancellation checkpoints -- you cannot assume that an
[`await`][await] on one of these operations will give pending [`CancelledError`][cancellederror]s a chance
to land.

| Operation | Suspends when... | Returns immediately when... | Basis |
|-----------|------------------|-----------------------------|-------|
| [`stream.read(n)`][stream-read-n] | The buffer does not yet have the data needed to produce a result, and EOF has not been reached | `#!py n == 0`, or buffered data already determines the result, or EOF already determines the result | Docs + source |
| [`stream.readline()`][stream-readline] | A full line is not yet buffered, and EOF has not been reached | A full line is already buffered, or EOF already determines the result | Docs + source |
| [`stream.readexactly(n)`][stream-readexactly-n] | Fewer than `n` bytes are buffered, and EOF has not been reached | `#!py n == 0`, or at least `n` bytes are already buffered | Docs + source |
| [`stream.readuntil(separator)`][stream-readuntil-separator] | The separator is not yet buffered, and EOF has not been reached | The separator is already buffered | Docs + source |
| [`Queue.get()`][queue-get] | The queue is empty | The queue has at least one item | Docs |
| [`Queue.put(item)`][queue-put-item] | The queue is full | The queue has space, or the queue is unbounded | Docs |
| [`Queue.join()`][queue-join] | The unfinished-task count is greater than 0 | The unfinished-task count is already 0 | Source |
| [`Lock.acquire()`][lock-acquire] | The lock is held by another task | The lock is free | Docs + source |
| [`Event.wait()`][event-wait] | The event is not set | The event is already set | Docs |
| [`Condition.wait_for(predicate)`][condition-wait-for-predicate] | `#!py predicate()` is false, so one or more `#!py wait()` calls are needed | `#!py predicate()` is already true on entry | Source |
| [`Semaphore.acquire()`][semaphore-acquire] | The internal counter is 0 | The counter is greater than 0 | Docs |
| [`Barrier.wait()`][barrier-wait] | The barrier still needs more parties, or a previous cycle is draining or resetting | In CPython 3.11, this call is the final required party and the barrier is already in the normal filling state | Docs + source |
| [`stream.drain()`][stream-drain] | The write buffer is above the high-water mark, or the closing path needs a loop turn to surface an error | The buffer is below the high-water mark and there is nothing else to wait for | Docs + source |
| `#!py await task` | The task is still running | The task is already done -- it returns its result (or raises) immediately | Language + asyncio semantics |
| `#!py await future` | The future is not yet resolved | The future already has a result or exception | Language + asyncio semantics |
| [`asyncio.wait_for(aw, timeout)`][asyncio-wait-for-aw-timeout] | `#!py timeout > 0`, or `#!py timeout <= 0` and the awaitable is not already done | `#!py timeout is None` and the awaitable is already done, or `#!py timeout <= 0` and it is already done | CPython 3.11 source |

!!! warning

    **`#!py await task` on an already-finished task does not suspend.** This is
    a common source of confusion. If you are counting on [`await`][await] as a
    checkpoint for cancellation delivery, and the awaitable has already
    completed, the cancellation check never happens. Insert an explicit
    `#!py await asyncio.sleep(0)` when you need a guaranteed checkpoint.

Note that [`stream.drain()`][stream-drain] is particularly subtle. A common pattern is to call
[`stream.write(data)`][stream-write-data] followed by `#!py await stream.drain()`. Because
`#!py write()` is synchronous and [`drain()`][drain] often returns immediately,
a sequence of small writes may execute entirely without yielding. If you need
a checkpoint between writes, add an explicit `#!py await asyncio.sleep(0)`.

---

## Never Suspends

As a general rule, plain synchronous calls do not suspend. If there is no
[`await`][await], there is no checkpoint, and no other task can interleave during
that call.

For most synchronous asyncio methods, that rule is enough. The only ones worth
calling out here are the methods people often *mistake* for checkpoints, or
that trigger asynchronous consequences later without yielding themselves.

| Operation | Why it is easy to misread |
|-----------|---------------------------|
| [`stream.write(data)`][stream-write-data] / [`write_eof()`][stream-write-eof] / [`close()`][stream-close] | They start network-related work, but the call itself only buffers data or initiates closing. Use [`drain()`][drain] or [`wait_closed()`][wait-closed] to actually wait for progress. |
| [`Event.set()`][event-set], [`Lock.release()`][lock-release], [`Condition.notify()`][condition-notify] / [`notify_all()`][notify-all], [`Semaphore.release()`][semaphore-release] | They can wake waiting tasks, but the current task keeps running until its next real suspension point. |
| [`task.cancel(msg=...)`][task-cancel-msg] | It requests cancellation, but the [`CancelledError`][cancellederror] is delivered later when the target task next truly suspends. |
| [`future.set_result()`][future-set-result] / [`future.set_exception()`][future-set-exception] | They resolve a future and schedule awaiters to resume later, but the call itself does not yield. |
| [`Queue.put_nowait(item)`][queue-put-nowait-item], [`Queue.get_nowait()`][queue-get-nowait], [`Queue.task_done()`][queue-task-done] | These are immediate queue operations with no suspension path. |

---

## Implications

Three practical consequences follow from this table.

### Cancellation delivery requires a real checkpoint

[`task.cancel()`][task-cancel]
does not raise [`CancelledError`][cancellederror] immediately. The official docs say it is
thrown into the coroutine on the next cycle of the event loop. In the mental
model used by this guide, that means the task has to hit a real suspension
point so the loop can run it again. If the task enters a long stretch of
synchronous code, or only [`await`][await]s things that resolve immediately
(the "conditionally suspends" rows in their fast-path state), cancellation
stays pending indefinitely. This is why
[`asyncio.timeout()`][asyncio-timeout]
can appear to not work: the deadline fires, `#!py cancel()` is called, but the task
never reaches a checkpoint where the [`CancelledError`][cancellederror] can be delivered. The fix
is to ensure long-running code periodically hits a real checkpoint --
`#!py await asyncio.sleep(0)` is the standard idiom.

### Starvation is caused by missing checkpoints

The asyncio event loop is cooperative: a task runs until it voluntarily
suspends. If a task loops over operations that never suspend (or only
conditionally suspend and the fast path keeps winning), no other task gets a
turn. This makes the program *appear* single-threaded and can cause timeouts
and watchdogs to fire late or not at all. The cure is the same: sprinkle
`#!py await asyncio.sleep(0)` at regular intervals in CPU-bound or tight loops.
Better yet, offload heavy computation to a thread with
[`asyncio.to_thread()`][asyncio-to-thread]
so the event loop stays responsive.

### Shared state is safe between checkpoints

On the flip side, cooperative scheduling gives you a strong guarantee: between
two consecutive real suspension points, no other task can run. This means you
do not need a lock to protect a read-modify-write sequence *as long as there
is no [`await`][await] (or only non-suspending [`await`][await]s) between the read and
the write*. Understanding exactly which operations suspend is what lets you
distinguish the safe cases from the unsafe ones -- and that is the purpose of
this table.

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
