---
title: Cancellation and Timeouts
description: >-
  Understand CancelledError, asyncio.timeout(), and asyncio.timeout_at(). Learn
  how cooperative cancellation works, how to write cancellation-safe code, and
  how timeouts interact with TaskGroup.
---

# Cancellation and Timeouts

Cancellation is what makes task lifetimes *real*. Without it, timeouts are
wishes and [`TaskGroup`][taskgroup] has no way to shut down children when a
sibling fails. Everything you saw in [Concurrent Tasks](concurrent-tasks.md) --
sibling cancellation, the clean [`async with`][async-with] guarantee -- relies
on the machinery covered here.

## Cancellation

Cancellation is the mechanism asyncio uses to stop a coroutine. This mechanism
uses exceptions as a delivery system. When something decides your task should
end -- a timeout expiring, a [`TaskGroup`][taskgroup] tearing down siblings --
the event loop arranges for a [`CancelledError`][cancellederror] to be raised
at the next *checkpoint* (an [`await`][await] where the coroutine suspends).
The exception then unwinds the call stack normally, running `#!py finally`
blocks and [`__aexit__`][aexit] methods on the way out, just like any other
exception.

The key detail: [`CancelledError`][cancellederror] inherits from
[`BaseException`][baseexception], **not** [`Exception`][exception]. This means
a plain `#!py except Exception:` will not catch it. That is deliberate --
cancellation should pass through most error handlers undisturbed. If it were a
subclass of `Exception`, every `#!py except Exception:` in your code would
accidentally swallow it.

!!! Note

    [`CancelledError`][cancellederror] is not delivered at arbitrary points
    like a POSIX signal. It only appears at [`await`][await] expressions -- the
    same checkpoints discussed in the [Getting Started](getting-started.md)
    section. Between checkpoints, your code runs uninterrupted. This is the
    *cooperative cancellation* model: the framework requests cancellation, and
    your code cooperates by hitting an [`await`][await].

### Never Swallow a `#!py CancelledError`

The single most important cancellation rule: **never catch
[`CancelledError`][cancellederror] and suppress it.** If you do, the caller
that requested cancellation will never know it happened, and your program's
lifetime guarantees fall apart.

Let's see what "swallowing" looks like. Here is a function that tries to be
helpful by returning a fallback value when it gets cancelled:

```python title="swallow_cancel_broken.py" hl_lines="7 9"
import asyncio

async def fetch_with_fallback(url: str) -> str:
    try:
        await asyncio.sleep(10) # (1)!
        return f"Data from {url}"
    except asyncio.CancelledError:
        print("fetch: cancelled, returning fallback")
        return "default" # (2)!

async def main() -> None:
    async with asyncio.timeout(1):
        result: str = await fetch_with_fallback("https://example.com")
    print(f"Got: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

1. Simulate slow network.
2. **BUG:** swallows cancellation.

```text title="$ python swallow_cancel_broken.py"
fetch: cancelled, returning fallback
Got: default
```

The timeout fired after one second and tried to cancel the work. But
`fetch_with_fallback` caught the [`CancelledError`][cancellederror] and
returned `#!py "default"` -- defeating the timeout entirely. This is a real bug
in production code: timeouts that don't actually time out.

The fix: catch the error, do your cleanup, and **re-raise**:

```python title="swallow_cancel_fixed.py" hl_lines="7 9"
import asyncio

async def fetch_with_cleanup(url: str) -> str:
    try:
        await asyncio.sleep(10)
        return f"Data from {url}"
    except asyncio.CancelledError:
        print("fetch: cancelled, cleaning up")
        raise # (1)!

async def main() -> None:
    try:
        async with asyncio.timeout(1):
            result: str = await fetch_with_cleanup("https://example.com")
            print(f"Got: {result}")
    except TimeoutError:
        print("Timed out as expected")

if __name__ == "__main__":
    asyncio.run(main())
```

1. Always re-raise!

```text title="$ python swallow_cancel_fixed.py"
fetch: cancelled, cleaning up
Timed out as expected
```

Cancellation propagates correctly now. The
[`asyncio.timeout()`][asyncio-timeout] context manager converts it to
[`TimeoutError`][timeouterror] at the [`async with`][async-with] boundary, and
the caller handles the timeout cleanly.

!!! Danger

    If you see `#!py except asyncio.CancelledError:` without a `#!py raise` in
    any code path, that is almost always a bug.

    Because [`CancelledError`][cancellederror] inherits from
    [`BaseException`][baseexception], a bare `#!py except:` or `#!py except
    BaseException:` will catch it too.

    The "Never Swallow" rule applies in these cases as well, and you should
    always re-raise `CancelledError` if you catch it.

### Cleanup with `#!py try`/`#!py finally`

Most of the time you don't need to catch [`CancelledError`][cancellederror] at
all. If your cleanup should run regardless of *how* the coroutine exits --
success, exception, or cancellation -- use a `#!py finally` block:

```python title="finally_cleanup.py" hl_lines="5 8"
import asyncio

async def worker(name: str) -> None:
    print(f"{name}: starting")
    try:
        await asyncio.sleep(10)
        print(f"{name}: finished")
    finally:
        print(f"{name}: cleaning up")

async def main() -> None:
    try:
        async with asyncio.timeout(0.5):
            await worker("alpha")
    except TimeoutError:
        print("Timed out")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python finally_cleanup.py"
alpha: starting
alpha: cleaning up
Timed out
```

The `#!py finally` block ran even though the coroutine was cancelled. Reach for
`#!py try`/`#!py finally` first; reserve `#!py except CancelledError` for the
rare cases where cleanup is *specific* to cancellation (e.g., logging a
different message).

!!! Danger

    If the code in your `#!py finally` block can raise an exception, that
    exception will propagate instead of the original `CancelledError`. This can
    lead to unexpected behavior where the cancellation is effectively ignored
    because the new exception takes precedence.

    This is another instance where the "Never Swallow" rule applies, **your
    `#!py finally` block should never raise**.

    If the cleanup is best-effort and can still fail, put a nested
    `#!py try`/`#!py except Exception` inside the `#!py finally` block. That
    lets you log the cleanup failure without replacing the original
    cancellation:

    ```python
    async def worker(name: str) -> None:
        print(f"{name}: starting")
        try:
            await asyncio.sleep(10)
            print(f"{name}: finished")
        finally:
            try:
                print(f"{name}: cleaning up")
                # Cleanup code that can raise an exception
            except Exception as exc:
                print(f"{name}: cleanup failed with exception: {exc}")
    ```

    Use `#!py except Exception`, not a bare `#!py except:`, so
    [`CancelledError`][cancellederror] still propagates.

## Timeouts

[`asyncio.timeout()`][asyncio-timeout] is an async context manager that
enforces a deadline on the code inside it. If the block takes longer than the
specified number of seconds, asyncio cancels the current task and converts the
resulting [`CancelledError`][cancellederror] into a
[`TimeoutError`][timeouterror] at the [`async with`][async-with] boundary.

```python title="timeout_basic.py"
import asyncio

async def slow_operation() -> str:
    await asyncio.sleep(5)
    return "done"

async def main() -> None:
    try:
        async with asyncio.timeout(1):
            result: str = await slow_operation()
            print(result)
    except TimeoutError:
        print("Operation timed out after 1 second")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python timeout_basic.py"
Operation timed out after 1 second
```

There are two important things to understand here. First,
[`asyncio.timeout()`][asyncio-timeout] cancels the *current task*. The
[`CancelledError`][cancellederror] is raised at whatever [`await`][await] the
task is suspended on. Second, the conversion from
[`CancelledError`][cancellederror] to [`TimeoutError`][timeouterror] only
happens at the [`async with`][async-with] boundary. If your code receives a
[`CancelledError`][cancellederror] from *outside* the timeout scope (e.g., a
parent [`TaskGroup`][taskgroup] shutting down), that cancellation passes
through unchanged -- it does not become a [`TimeoutError`][timeouterror].

You can pass `#!py None` as the delay to create a timeout that never fires --
useful when the timeout value comes from configuration and `#!py None` means
"no limit":

```python
delay: float | None = None  # From config
async with asyncio.timeout(delay):
    await slow_operation()
```

!!! Tip "Absolute Deadlines"

    [`asyncio.timeout_at()`][asyncio-timeout-at] works like
    [`asyncio.timeout()`][asyncio-timeout] but takes an *absolute* deadline
    based on the event loop's internal clock, rather than a relative delay.

    It is a more advanced feature as it requires to get the current loop time
    via [`asyncio.get_running_loop()`][asyncio-get-running-loop]. This is
    covered in the [Loop Access and
    Inspection](../the-low-level-toolkit/loop-access-and-inspection.md) section
    in [The Low-Level Toolkit](../the-low-level-toolkit/index.md), so we won't
    get into it in detail here, but you should be aware of its existence in
    case you need it.

!!! Tip "Trio"

    [`asyncio.timeout()`][asyncio-timeout] is equivalent to
    [`trio.fail_after()`][trio-fail-after]. The main difference is that
    [Trio][trio-docs] uses [cancel scopes][trio-cancel-scopes] as an explicit
    concept, while asyncio's timeout context managers handle the scoping
    implicitly.

### Timeouts and Task Groups

Timeouts and [`TaskGroup`][taskgroup]s work together in two natural patterns.

#### Timeout around a `#!py TaskGroup`

The entire group must finish within the deadline. When the timeout fires, it
cancels the current task, which triggers the [`TaskGroup`][taskgroup] to cancel
all its children:

```python title="timeout_around_group.py"
import asyncio

async def fetch(url: str) -> str:
    await asyncio.sleep(2)
    return f"Data from {url}"

async def main() -> None:
    try:
        async with asyncio.timeout(1):
            async with asyncio.TaskGroup() as tg:
                tg.create_task(fetch("https://example.com/a"), name="fetch-a")
                tg.create_task(fetch("https://example.com/b"), name="fetch-b")
                tg.create_task(fetch("https://example.com/c"), name="fetch-c")
    except TimeoutError:
        print("All fetches cancelled -- group took too long")
    else:
        print("All fetches completed successfully")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python timeout_around_group.py"
All fetches cancelled -- group took too long
```

The timeout fires after one second, cancelling the host task. The
[`TaskGroup`][taskgroup] sees the cancellation and cancels all three children.
Clean and predictable.

!!! Warning

    **Always put the timeout *around* the [`TaskGroup`][taskgroup], not inside
    it.**

    If you change the above code to put the timeout around the `#!py
    tg.create_task()` calls instead the whole group, it will never time out (it
    will finish after two seconds):

    ```python title="timeout_around_group_broken.py" hl_lines="1-2"
    async with asyncio.TaskGroup() as tg: # (1)!
        async with asyncio.timeout(1):
            tg.create_task(fetch("https://example.com/a"), name="fetch-a")
            tg.create_task(fetch("https://example.com/b"), name="fetch-b")
            tg.create_task(fetch("https://example.com/c"), name="fetch-c")
        # (2)!
    # (3)!
    ```

    1. Reversed order -- timeout is inside the group.
    2. At this point the timeout scope is already gone. Until this point there
       are even no checkpoints possible (no `#!py await`), so the timeout can't
       fire.
    3. Here is the first opportunity for a cancellation, when the `TaskGroup`
       waits for the children to finish, but the timeout blcok is already gone
       here.

    ```text title="$ python timeout_around_group_broken.py"
    All fetches completed successfully
    ```

    This is what happens:

    - [`asyncio.timeout()`][asyncio-timeout] only cancels the *current task*.
    - `#!py tg.create_task(...)` schedules a new task and returns immediately.
    - The host task leaves the timeout block almost instantly (there are no
      `#!py await`s inside the `#!py timeout()` block), there are no
      checkpoints, and thus no cancellation opportunities and no timeout
      possible.
    - Later, [`TaskGroup`][taskgroup] waits for the child in its own
      [`__aexit__`][aexit] -- *outside* the timeout.

#### Individual timeouts inside `TaskGroup` children

Each child manages its own deadline independently:

```python title="timeout_inside_group.py"
import asyncio

async def fetch_with_timeout(url: str, deadline: float) -> str:
    try:
        async with asyncio.timeout(deadline):
            await asyncio.sleep(2)
            return f"Data from {url}"
    except TimeoutError:
        return f"TIMEOUT for {url}"

async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(
            fetch_with_timeout("https://example.com/fast", 3.0),
            name="fetch-fast",
        )
        t2 = tg.create_task(
            fetch_with_timeout("https://example.com/slow", 0.5),
            name="fetch-slow",
        )

    print(t1.result())
    print(t2.result())

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python timeout_inside_group.py"
Data from https://example.com/fast
TIMEOUT for https://example.com/slow
```

Here the second task timed out, but it handled the
[`TimeoutError`][timeouterror] internally. Since it didn't *raise*, the
[`TaskGroup`][taskgroup] didn't cancel the first task. Choose based on whether
the timeout is a property of the whole group or of individual operations.

!!! Warning

    If a child task's timeout raises [`TimeoutError`][timeouterror] and that
    error is *not* caught inside the child, it propagates into the
    [`TaskGroup`][taskgroup], which treats it as a child failure and cancels
    all siblings. Make sure individual timeouts are handled within the child if
    you want the group to continue.

[async-with]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[await]: https://docs.python.org/3/reference/expressions.html#await
[aexit]: https://docs.python.org/3/reference/datamodel.html#object.__aexit__
[baseexception]: https://docs.python.org/3/library/exceptions.html#BaseException
[exception]: https://docs.python.org/3/library/exceptions.html#Exception
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[asyncio-shield]: https://docs.python.org/3/library/asyncio-task.html#asyncio.shield
[timeouterror]: https://docs.python.org/3/library/exceptions.html#TimeoutError
[trio-fail-after]: https://trio.readthedocs.io/en/stable/reference-core.html#trio.fail_after
[trio-docs]: https://trio.readthedocs.io/en/stable/
[trio-cancel-scopes]: https://trio.readthedocs.io/en/stable/reference-core.html#cancellation-and-timeouts
[asyncio-timeout-at]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout_at
[asyncio-get-running-loop]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop
[expired]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Timeout.expired
