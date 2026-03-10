---
title: Tasks and Futures
description: >-
  Understand asyncio.Future and asyncio.Task — the concrete objects that
  make concurrency work. Learn how create_task() schedules coroutines,
  the task lifecycle, and how tasks drive coroutines forward one await
  at a time.
---

# Tasks and Futures

The event loop is the scheduler, but it doesn't do much by itself. It needs
*objects* it can schedule -- things that represent "work in progress" and can
report back when they're done. Those objects are
[`asyncio.Future`][asyncio-future]
and its subclass
[`asyncio.Task`][asyncio-task].
Together, they are the concrete machinery that makes concurrency work. The
event loop spins, futures hold eventual results, and tasks drive coroutines
forward one [`await`][await] at a time.

## [`asyncio.Future`][asyncio-future]

A *future* is a container for a value that doesn't exist yet. You can think of
it as an empty box with a label that says "result goes here." Someone will put
a value in later -- or an exception, if things go wrong. Until then, the
future is *pending*.

The API is small:

- **`#!py .done()`** -- returns `#!py True` if the future has a result, an exception, or
  was cancelled. Returns `#!py False` while it's still pending.
- **`#!py .result()`** -- returns the value. Raises `InvalidStateError` if the
  future isn't done yet, or re-raises the stored exception if one was set.
- **`#!py .exception()`** -- returns the stored exception (or `#!py None` if the future
  completed successfully). Raises `InvalidStateError` if not done.
- **`#!py .set_result(value)`** -- fills the box with a value and marks the future
  done. Can only be called once.
- **`#!py .set_exception(exc)`** -- fills the box with an exception. Can only be
  called once.
- **`#!py .add_done_callback(fn)`** -- registers a function that will be called
  (via [`call_soon()`][call-soon]) when the future completes. You can add multiple
  callbacks; they fire in the order they were added.
- **`#!py .cancel()`** -- marks the future as cancelled. Any callbacks are still
  called.

You can also [`await`][await] a future. When you do, the current coroutine suspends
until the future is done, then the [`await`][await] expression returns the future's
result (or raises its exception).

!!! note

    Application code rarely creates futures directly. They are the low-level
    plumbing that asyncio's internals -- transports, protocols, and the loop
    itself -- use to communicate results between components. You will see
    them when you work with the low-level APIs in Chapter 4 (callbacks,
    transports, [`loop.create_future()`][loop-create-future]). For now, understanding what they
    *are* is enough.

Here is a minimal example that shows the lifecycle. You would not write this in
a real program, but it makes the mechanics clear:

```python title="future_lifecycle.py"
import asyncio


async def fill_future(fut: asyncio.Future[str]) -> None:
    await asyncio.sleep(1)
    fut.set_result("hello from the future")


async def main() -> None:
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[str] = loop.create_future()

    print(f"done? {fut.done()}")           # False -- still pending

    asyncio.create_task(fill_future(fut))  # schedule someone to fill it
    result: str = await fut                # suspend until filled
    print(f"done? {fut.done()}")           # True
    print(f"result: {fut.result()}")       # "hello from the future"


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python future_lifecycle.py"
done? False
done? True
result: hello from the future
```

The key insight: a future *decouples* the production of a value from its
consumption. The code that sets the result doesn't need to know who is waiting
for it, and the code that awaits doesn't need to know who will provide it.
This decoupling is what allows the event loop to wire together callbacks,
I/O completions, and coroutines into a single coherent system.

## [`asyncio.Task`][asyncio-task]

A *task* is a future that wraps a coroutine and drives it on the event loop.
Where a plain future is a passive container (someone else must call
[`set_result()`][set-result]), a task is *active* -- it repeatedly resumes the coroutine,
handles whatever it yields, and eventually sets its own result when the
coroutine returns.

[`asyncio.Task`][asyncio-task] is a subclass of [`asyncio.Future`][asyncio-future], so everything you just
learned about futures applies to tasks too: `#!py .done()`, `#!py .result()`,
`#!py .exception()`, `#!py .cancelled()`, `#!py await task`, and done callbacks all work the
same way. The difference is that nobody calls `#!py task.set_result()` from the
outside -- the task does it itself when the coroutine finishes.

When you create a task, two things happen immediately:

1. The coroutine object is stored inside the task.
2. The task schedules its first *step* via [`call_soon()`][call-soon] on the event loop.

That second point is important: the coroutine does not start running the
instant you create the task. It starts on the *next iteration* of the event
loop, when the loop processes the [`call_soon()`][call-soon] callback. This is why
[`create_task()`][create-task] returns immediately -- it just puts work on the queue.

## [`asyncio.create_task()`][asyncio-create-task]

[`asyncio.create_task()`][asyncio-create-task]
is the function that wraps a coroutine in a [`Task`][task] and schedules it on the
running loop. In Chapter 1 you saw `#!py tg.create_task()` -- the [`TaskGroup`][taskgroup]
method that gives tasks an owner. Under the hood, `#!py TaskGroup.create_task()`
calls [`asyncio.create_task()`][asyncio-create-task] and then tracks the resulting task so it can
enforce structured concurrency. This section is about the raw function
underneath.

```python title="create_task_demo.py"
import asyncio


async def compute(n: int) -> int:
    await asyncio.sleep(0.5)
    return n * n


async def main() -> None:
    task: asyncio.Task[int] = asyncio.create_task(compute(7), name="square-7")
    print(f"task name: {task.get_name()}")
    print(f"task done? {task.done()}")

    result: int = await task
    print(f"task done? {task.done()}")
    print(f"result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python create_task_demo.py"
task name: square-7
task done? False
task done? True
result: 49
```

The `name` parameter is optional. If you omit it, asyncio assigns a default
like `#!py "Task-1"`, `#!py "Task-2"`, etc. You can also change the name after
creation with `#!py .set_name()`:

```python
task.set_name("new-name")
print(task.get_name())  # "new-name"
```

Task names appear in tracebacks and debug output, so naming your tasks -- even
with something short like `#!py f"fetch-{url}"` -- pays off immediately when
something goes wrong.

!!! info

    **Prefer `#!py TaskGroup.create_task()` over bare [`asyncio.create_task()`][asyncio-create-task].**
    A [`TaskGroup`][taskgroup] gives every task an owner, ensures exceptions propagate,
    and prevents orphaned tasks. Bare [`create_task()`][create-task] is a building block
    -- it is what [`TaskGroup`][taskgroup] calls internally -- but in application code
    the unowned version is almost always a mistake. See the
    [Concurrent Tasks](../the-basics/concurrent-tasks.md) section in
    Chapter 1 for the full argument.

## Task Lifecycle

Every task starts in the *pending* state and eventually moves to *done*. There
are exactly three ways a task can become done:

1. **Result** -- the coroutine returned a value. The task stores it. Success.
2. **Exception** -- the coroutine raised an exception. The task stores it.
   Failure.
3. **Cancelled** -- someone called [`task.cancel()`][task-cancel] and the cancellation was
   not suppressed. The task is marked cancelled.

Once a task is done, it stays done -- there is no going back to pending. The
inspection methods tell you which state you're in:

| Method          | Pending | Result | Exception | Cancelled |
|-----------------|---------|--------|-----------|-----------|
| `#!py .done()`       | `#!py False` | `#!py True` | `#!py True`    | `#!py True`    |
| `#!py .cancelled()`  | `#!py False` | `#!py False`| `#!py False`   | `#!py True`    |
| `#!py .result()`     | raises `InvalidStateError` | returns value | re-raises exception | raises [`CancelledError`][cancellederror] |
| `#!py .exception()`  | raises `InvalidStateError` | returns `#!py None` | returns exception | raises [`CancelledError`][cancellederror] |

The following example walks through all three outcomes:

```python title="task_lifecycle.py"
import asyncio


async def succeed() -> str:
    return "ok"


async def fail() -> str:
    raise ValueError("something broke")


async def hang_forever() -> str:
    await asyncio.sleep(3600)
    return "unreachable"


async def main() -> None:
    # Outcome 1: result
    t1: asyncio.Task[str] = asyncio.create_task(succeed(), name="t1")
    await t1
    print(f"t1 done={t1.done()}, cancelled={t1.cancelled()}, result={t1.result()!r}")

    # Outcome 2: exception
    t2: asyncio.Task[str] = asyncio.create_task(fail(), name="t2")
    try:
        await t2
    except ValueError:
        pass
    print(f"t2 done={t2.done()}, cancelled={t2.cancelled()}, exception={t2.exception()!r}")

    # Outcome 3: cancelled
    t3: asyncio.Task[str] = asyncio.create_task(hang_forever(), name="t3")
    await asyncio.sleep(0)  # let t3 start
    t3.cancel()
    try:
        await t3
    except asyncio.CancelledError:
        pass
    print(f"t3 done={t3.done()}, cancelled={t3.cancelled()}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python task_lifecycle.py"
t1 done=True, cancelled=False, result='ok'
t2 done=True, cancelled=False, exception=ValueError('something broke')
t3 done=True, cancelled=True
```

Notice the pattern: `#!py await task` either returns the result or re-raises
whatever ended the task (the stored exception, or [`CancelledError`][cancellederror]). Calling
`#!py .result()` on a done task does the same thing without suspending -- but if
you call it on a task that isn't done yet, you get `InvalidStateError`.

!!! tip

    After a [`TaskGroup`][taskgroup] block exits normally, every task in the group is
    guaranteed done. That is why the
    [Collecting Results](../the-basics/concurrent-tasks.md) pattern
    calls `#!py .result()` *after* the [`async with`][async-with] block -- it is always safe
    there.

## Task References

Tasks are Python objects, and Python garbage-collects objects that nobody
references. This leads to a subtle footgun: if you create a task and don't
store it anywhere, the garbage collector may destroy it while it's still
running.

```python
# lost_reference.py — DON'T DO THIS
import asyncio


async def background_work() -> None:
    await asyncio.sleep(1)
    print("work finished!")


async def main() -> None:
    asyncio.create_task(background_work())  # no reference stored!
    await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
```

If the garbage collector runs before the task completes, you will see this
warning:

```text
Task was destroyed but it is pending!
```

The task was created, scheduled, and then -- because nothing in your code held
a reference to the [`Task`][task] object -- it became eligible for collection. The
event loop holds a *weak reference* to running tasks, which is not enough to
keep them alive.

The fix is straightforward: store a reference. A local variable, a list, a
set -- anything that keeps the object alive until the task is done:

```python
async def main() -> None:
    task = asyncio.create_task(background_work())  # reference stored
    await task
```

!!! warning

    This is one more reason to prefer [`TaskGroup`][taskgroup]. When you call
    `#!py tg.create_task()`, the group stores a strong reference to the task
    internally. You never have to worry about lost references inside a
    [`TaskGroup`][taskgroup] scope.

## How Tasks Drive Coroutines

You now know that a task wraps a coroutine and drives it on the event loop.
But what does "drive" actually mean? Here is a simplified picture of what
happens inside a task. This is *not* the real implementation (which handles
many edge cases), but it captures the essential mechanism:

```python
# Pseudocode -- not real asyncio source
class Task(Future):
    def __init__(self, coro):
        super().__init__()
        self._coro = coro
        # Schedule the first step on the event loop
        self._loop.call_soon(self.__step)

    def __step(self):
        try:
            # Resume the coroutine
            result = self._coro.send(None)
        except StopIteration as exc:
            # Coroutine returned -- set the task's result
            self.set_result(exc.value)
        except BaseException as exc:
            # Coroutine raised -- set the task's exception
            self.set_exception(exc)
        else:
            # Coroutine yielded a future it's waiting on.
            # When that future completes, run __step again.
            result.add_done_callback(self.__step)
```

Here is what happens, step by step:

1. **Creation.** The task is created with a coroutine. It calls
   `#!py call_soon(self.__step)` to schedule the first step on the loop's ready
   queue.

2. **First step.** On the next loop iteration, `__step` runs. It calls
   `#!py coro.send(None)`, which resumes the coroutine from the beginning. The
   coroutine runs until it hits an [`await`][await] on something that isn't ready yet
   -- typically a future representing an I/O completion or a timer.

3. **Suspension.** The [`await`][await] causes the coroutine to yield that future back
   to the task. The task registers `__step` as a done callback on the yielded
   future. Now the task is suspended -- nothing else happens until that
   future completes.

4. **Resumption.** When the awaited future completes (because I/O finished, a
   timer expired, etc.), its done callbacks fire. That calls `__step` again,
   which calls `#!py coro.send(None)` again, resuming the coroutine right after
   the [`await`][await] that suspended it. This cycle repeats.

5. **Completion.** Eventually the coroutine either returns a value (raising
   `StopIteration` -- that's how Python generators and coroutines signal
   completion) or raises an exception. The task catches this, calls
   [`set_result()`][set-result] or [`set_exception()`][set-exception] on itself, and fires its own done
   callbacks.

This send-yield-callback loop is the heartbeat of asyncio concurrency. Every
[`await`][await] in your code is a point where the coroutine can suspend and the loop
can go service other tasks. When the thing being awaited finishes, the loop
comes back and picks up where it left off.

!!! note

    The real implementation in CPython is in
    [`_asyncio.Task`](https://github.com/python/cpython/blob/main/Modules/_asynciomodule.c)
    (C code for performance) with a Python fallback in
    [`asyncio.tasks`](https://github.com/python/cpython/blob/main/Lib/asyncio/tasks.py).
    The C version has the same structure but adds optimizations for common
    cases, cancellation handling, and context variable propagation. The
    pseudocode above is the mental model you need; read the source when you
    want the full picture.

---

[set-result]: https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_result
[async-with]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[set-exception]: https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.set_exception
[asyncio-future]: https://docs.python.org/3/library/asyncio-future.html#asyncio.Future
[asyncio-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task
[await]: https://docs.python.org/3/reference/expressions.html#await
[call-soon]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_soon
[loop-create-future]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.create_future
[create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[asyncio-create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[task-cancel]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError