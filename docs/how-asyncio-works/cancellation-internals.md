---
title: Cancellation Internals
description: >-
  Explore the internal cancellation protocol — task.cancel(),
  task.cancelling(), task.uncancel(), and how asyncio.timeout() and
  TaskGroup coordinate cancellation behind the scenes.
---

# Cancellation Internals

Chapter 1 taught you the user-facing rules: `CancelledError` is how asyncio
asks your code to stop, you must never swallow it, and `asyncio.timeout()`
converts it into `TimeoutError` at the `async with` boundary. Those rules are
enough to write correct programs. This section explains the machinery that
makes those rules *work* -- the internal protocol that `timeout()`, `TaskGroup`,
and the event loop use to coordinate cancellation behind the scenes.

You are not expected to use these APIs in normal application code. But when
cancellation behaves in a way you don't expect -- a timeout that "doesn't fire,"
a `TaskGroup` that seems to cancel too much or too little -- understanding the
internals will tell you exactly what happened.

## `task.cancel()`

[`Task.cancel(msg=None)`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel)
is how cancellation is *requested*. When you call it, the event loop arranges
for a `CancelledError` to be thrown into the task at the next checkpoint -- the
next `await` where the coroutine suspends.

```python
# cancel_basic.py
import asyncio


async def slow_work() -> str:
    print("slow_work: starting")
    await asyncio.sleep(10)
    print("slow_work: finished")
    return "done"


async def main() -> None:
    task: asyncio.Task[str] = asyncio.create_task(slow_work())
    await asyncio.sleep(0.1)  # Let the task start

    task.cancel()             # Request cancellation
    try:
        await task
    except asyncio.CancelledError:
        print(f"task.cancelled() = {task.cancelled()}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python cancel_basic.py
slow_work: starting
task.cancelled() = True
```

Two things to notice. First, calling `task.cancel()` does not immediately
stop the task. It schedules a `CancelledError` to be raised at the *next*
`await`. Between the call to `cancel()` and the next checkpoint, the task runs
normally. Second, the task has to *cooperate*. If the task catches
`CancelledError` and suppresses it (the cardinal rule violation from Chapter 1),
cancellation silently fails.

You can pass an optional `msg` argument to attach context to the
`CancelledError`:

```python
task.cancel(msg="parent timed out")
```

The message appears in the exception's `args`, which can be helpful for
debugging when multiple cancellation sources exist.

!!! note

    `task.cancel()` returns `True` if the cancellation was successfully
    scheduled, and `False` if the task is already done. A return value of
    `True` does **not** mean the task *will* be cancelled -- only that the
    request was delivered. The task can still catch and suppress the error.

## The Cancellation Counter

Here is where the internals get interesting. Cancellation is not a boolean
flag -- it is a *counter*.

Every `Task` keeps an internal count of how many pending cancel requests it
has received. Each call to `task.cancel()` increments this counter by one.
You can read the current value with
[`task.cancelling()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancelling):

```python
# cancelling_counter.py
import asyncio


async def inspect_cancellation() -> None:
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        print(f"cancelling() = {asyncio.current_task().cancelling()}")
        raise


async def main() -> None:
    task: asyncio.Task[None] = asyncio.create_task(inspect_cancellation())
    await asyncio.sleep(0.1)

    task.cancel(msg="first")
    task.cancel(msg="second")
    task.cancel(msg="third")

    try:
        await task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python cancelling_counter.py
cancelling() = 3
```

Three calls to `cancel()`, so `cancelling()` returns 3. Only one
`CancelledError` is raised -- the counter tracks how many *sources* requested
cancellation, not how many exceptions will appear.

[`Task.uncancel()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.uncancel)
decrements the counter by one. If the counter reaches zero, the task is no
longer considered "being cancelled" -- it can resume normal execution.

```python
# uncancel_demo.py
import asyncio


async def resilient_worker() -> str:
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        me = asyncio.current_task()
        assert me is not None
        print(f"before uncancel: cancelling() = {me.cancelling()}")
        me.uncancel()
        print(f"after  uncancel: cancelling() = {me.cancelling()}")
        return "recovered"
    return "normal"


async def main() -> None:
    task: asyncio.Task[str] = asyncio.create_task(resilient_worker())
    await asyncio.sleep(0.1)

    task.cancel()

    result: str = await task
    print(f"result = {result}")
    print(f"task.cancelled() = {task.cancelled()}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python uncancel_demo.py
before uncancel: cancelling() = 1
after  uncancel: cancelling() = 0
result = recovered
task.cancelled() = False
```

The task caught the `CancelledError`, called `uncancel()` to bring the counter
back to zero, and returned a value instead of re-raising. Because the task
finished with a result rather than a `CancelledError`, `task.cancelled()` is
`False`.

!!! danger

    This is a demonstration of the mechanism, not a pattern to follow.
    Calling `uncancel()` in application code is almost always wrong -- it
    violates the "never swallow cancellation" rule from Chapter 1. The APIs
    exist for *framework* code like `asyncio.timeout()` and `TaskGroup`,
    which need to intercept one cancellation source while preserving others.

## How `asyncio.timeout()` Works Internally

You know from Chapter 1 that `asyncio.timeout()` raises `TimeoutError` when
the deadline expires. Here is the step-by-step mechanism that makes it happen:

1. **Entry (`__aenter__`).** The timeout context manager registers a timer
   callback with the event loop. If the delay is 2 seconds, it calls
   `loop.call_later(2, ...)` to schedule a callback at the deadline.

2. **Timer fires.** When the deadline arrives, the callback calls
   `task.cancel()` on the current task. This increments the cancellation
   counter from, say, 0 to 1.

3. **`CancelledError` is raised.** At the next checkpoint inside the `async
   with` block, the task receives a `CancelledError`. The error propagates up
   through your code, running `finally` blocks normally.

4. **Exit (`__aexit__`).** When the `CancelledError` reaches the `async with`
   boundary, the timeout's `__aexit__` method runs. It sees that the error is a
   `CancelledError` *and* that the timeout's own timer has fired. It calls
   `task.uncancel()`, decrementing the counter by one.

5. **Counter check.** If `uncancel()` brings the counter back to zero, the
   task is no longer in a "being cancelled" state. The timeout replaces the
   `CancelledError` with a `TimeoutError` and returns. Your code sees
   `TimeoutError`, not `CancelledError`.

This is why external cancellation passes through a timeout unchanged. Suppose
a parent `TaskGroup` cancels your task *while* a timeout is also active. The
counter goes to 2 (one from the `TaskGroup`, one from the timeout). When the
timeout's `__aexit__` calls `uncancel()`, the counter drops to 1 -- not zero.
The timeout sees that someone *else* still wants this task cancelled, so it
lets the `CancelledError` propagate instead of converting it to `TimeoutError`.

```python
# timeout_vs_external.py
import asyncio


async def inner() -> None:
    try:
        async with asyncio.timeout(10):  # Generous timeout -- won't fire
            await asyncio.sleep(60)
    except TimeoutError:
        print("inner: got TimeoutError")
    except asyncio.CancelledError:
        print("inner: got CancelledError (external cancellation)")
        raise


async def main() -> None:
    task: asyncio.Task[None] = asyncio.create_task(inner())
    await asyncio.sleep(0.1)

    task.cancel(msg="external shutdown")
    try:
        await task
    except asyncio.CancelledError:
        print("main: task was cancelled")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python timeout_vs_external.py
inner: got CancelledError (external cancellation)
main: task was cancelled
```

The timeout had a 10-second deadline and never fired. The external `cancel()`
call raised `CancelledError`, and the timeout's `__aexit__` recognized that
*it* did not cause the cancellation. The error passed through as a
`CancelledError`, not a `TimeoutError`. This is the counter at work.

## How `TaskGroup` Works Internally

`TaskGroup` uses the same cancel/uncancel protocol to implement sibling
cancellation. Here is what happens when a child task fails:

1. **A child raises.** One of the tasks spawned by `tg.create_task()` raises
   an exception (any exception, not just `CancelledError`).

2. **Sibling cancellation.** The `TaskGroup` calls `cancel()` on every other
   child task. This ensures all siblings wind down.

3. **Parent interruption.** The `TaskGroup` also calls `cancel()` on the
   *parent* task -- the task running the `async with asyncio.TaskGroup()` body.
   This interrupts whatever the parent is doing inside the group (typically
   another `await`), so the `__aexit__` can run promptly.

4. **Waiting.** The `TaskGroup`'s `__aexit__` waits for all children to finish
   (whether by completing, raising, or being cancelled).

5. **Uncancel and raise.** Once all children are done, the `TaskGroup` calls
   `uncancel()` on the parent task -- undoing the cancel it issued in step 3.
   It then raises an
   [`ExceptionGroup`](https://docs.python.org/3/library/builtins.html#ExceptionGroup)
   containing the original child failures.

The uncancel step is crucial. Without it, the parent task would remain in a
"being cancelled" state even after the `TaskGroup` has finished its cleanup.
The cancel/uncancel pair is temporary -- the `TaskGroup` cancels the parent
only to get its attention, then reverses it once cleanup is complete.

And just like `asyncio.timeout()`, this plays nicely with external
cancellation. If the parent was *already* being cancelled (counter at 1) when a
child also fails, the `TaskGroup` increments to 2, does its work, then
decrements back to 1. The external cancellation is preserved -- the parent
stays in a "being cancelled" state after the `TaskGroup` exits.

!!! note

    This is why you might see `CancelledError` propagate out of a
    `TaskGroup` even though the group itself raises `ExceptionGroup` for
    child failures. If the group was cancelled from *outside*, the external
    `CancelledError` survives the group's uncancel and continues upward.

## "Cancellation Requested" vs "Actually Cancelled"

The counter protocol creates an important distinction: calling `task.cancel()`
does not mean the task *will* end up cancelled.

A task's final state depends on how it finishes, not on what was requested:

- **`task.cancelled()`** returns `True` only if the task terminated because a
  `CancelledError` propagated all the way out of the coroutine. It is a
  statement about the task's *final state*, not about pending requests.

- **`task.cancelling()`** returns the current number of pending cancel
  requests. It is a statement about *right now*, and it changes over time as
  `cancel()` and `uncancel()` are called.

A task can have `cancel()` called on it and still finish normally. This is
exactly what happens with `asyncio.timeout()`: the timeout calls `cancel()`,
the `CancelledError` is caught by `__aexit__`, `uncancel()` brings the counter
to zero, and the task continues running whatever comes after the `async with`
block. The task's final `.cancelled()` state will be `False` -- it was never
"actually cancelled," even though cancellation was requested and delivered.

```python
# requested_vs_actual.py
import asyncio


async def main() -> None:
    task: asyncio.Task[None] = asyncio.create_task(asyncio.sleep(0.5))
    await asyncio.sleep(0)  # Let the task start

    task.cancel()
    print(f"after cancel():  cancelling() = {task.cancelling()}")

    try:
        await task
    except asyncio.CancelledError:
        pass

    print(f"after awaiting:  cancelled()  = {task.cancelled()}")
    print(f"                 cancelling() = {task.cancelling()}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python requested_vs_actual.py
after cancel():  cancelling() = 1
after awaiting:  cancelled()  = True
                 cancelling() = 0
```

Here the task had no `try`/`except`, so the `CancelledError` propagated out
and the task ended up in the cancelled state. But if the task had caught the
error and called `uncancel()` -- as `timeout()` does internally -- `cancelled()`
would be `False`.

## Why This Matters

For everyday code, the rules from Chapter 1 are all you need: don't swallow
`CancelledError`, use `asyncio.timeout()` for deadlines, and let `TaskGroup`
handle sibling cleanup. You will not call `cancel()`, `cancelling()`, or
`uncancel()` yourself.

But when something goes wrong in a complex program -- nested `TaskGroup`s
wrapped in timeouts, with multiple layers of cancellation in flight -- the
counter model is what you reach for. Here are the questions it answers:

- **"My timeout didn't raise `TimeoutError`."** Something inside the timeout
  block caught the `CancelledError` and suppressed it, so it never reached
  the timeout's `__aexit__`. The timeout could not convert what it never saw.

- **"I got `CancelledError` instead of `TimeoutError`."** There was an
  additional cancel request from outside the timeout. After the timeout called
  `uncancel()`, the counter was still positive, so the `CancelledError`
  propagated instead of being converted.

- **"A task in my `TaskGroup` wasn't cancelled."** If a child task catches
  `CancelledError` and calls `uncancel()` (or swallows the error entirely),
  the `TaskGroup`'s cancellation request is defeated. That child keeps running.

In all three cases, the explanation comes down to the counter: who incremented
it, who decremented it, and what the value was when a decision had to be made.

---
