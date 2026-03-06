# Cancellation and Timeouts

Previous: [Concurrent Tasks](concurrent-tasks.md)
Next: [Resource Management](resource-management.md)

Cancellation is what makes task lifetimes *real*. Without it, timeouts are
wishes and `TaskGroup` has no way to shut down children when a sibling fails.
Everything you saw in the previous section -- sibling cancellation, the clean
`async with` guarantee -- relies on the machinery covered here.

## What is `CancelledError`?

[`CancelledError`](https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError)
is the exception asyncio uses to tell a coroutine "stop what you're doing."
When something decides your task should end -- a timeout expiring, a
`TaskGroup` tearing down siblings -- the event loop arranges for a
`CancelledError` to be raised at the next *checkpoint* (an `await` where the
coroutine suspends). The exception then unwinds the call stack normally,
running `finally` blocks and `__aexit__` methods on the way out, just like any
other exception.

The key detail: `CancelledError` inherits from
[`BaseException`](https://docs.python.org/3/library/exceptions.html#BaseException),
**not** `Exception`. This means a plain `except Exception:` will not catch it.
That is deliberate -- cancellation should pass through most error handlers
undisturbed. If it were a subclass of `Exception`, every `except Exception:`
in your code would accidentally swallow it.

> [!NOTE]
> `CancelledError` is not delivered at arbitrary points like a POSIX signal. It
> only appears at `await` expressions -- the same checkpoints discussed in the
> [Getting Started](getting-started.md) section. Between checkpoints, your
> code runs uninterrupted. This is the *cooperative cancellation* model: the
> framework requests cancellation, and your code cooperates by hitting an
> `await`.

## The Cardinal Rule: Never Swallow Cancellation

The single most important cancellation rule: **never catch `CancelledError`
and suppress it.** If you do, the caller that requested cancellation will never
know it happened, and your program's lifetime guarantees fall apart.

Let's see what "swallowing" looks like. Here is a function that tries to be
helpful by returning a fallback value when it gets cancelled:

```python
# swallow_cancel_broken.py
import asyncio

async def fetch_with_fallback(url: str) -> str:
    try:
        await asyncio.sleep(10)  # Simulate slow network
        return f"Data from {url}"
    except asyncio.CancelledError:
        print("fetch: cancelled, returning fallback")
        return "default"  # BUG: swallows cancellation

async def main() -> None:
    async with asyncio.timeout(1):
        result: str = await fetch_with_fallback("https://example.com")
    print(f"Got: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python swallow_cancel_broken.py
fetch: cancelled, returning fallback
Got: default
```

The timeout fired after one second and tried to cancel the work. But
`fetch_with_fallback` caught the `CancelledError` and returned `"default"` --
defeating the timeout entirely. This is a real bug in production code:
timeouts that don't actually time out.

The fix: catch the error, do your cleanup, and **re-raise**:

```python
# swallow_cancel_fixed.py
import asyncio

async def fetch_with_cleanup(url: str) -> str:
    try:
        await asyncio.sleep(10)
        return f"Data from {url}"
    except asyncio.CancelledError:
        print("fetch: cancelled, cleaning up")
        raise  # Always re-raise

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

```text
$ python swallow_cancel_fixed.py
fetch: cancelled, cleaning up
Timed out as expected
```

Cancellation propagates correctly now. The `asyncio.timeout()` context manager
converts it to `TimeoutError` at the `async with` boundary, and the caller
handles the timeout cleanly.

> [!CAUTION]
> If you see `except asyncio.CancelledError:` without a `raise` in any code
> path, that is almost always a bug. Treat it the same way you would treat
> `except BaseException: pass` -- something has gone wrong.

## Cleanup with `try`/`finally`

Most of the time you don't need to catch `CancelledError` at all. If your
cleanup should run regardless of *how* the coroutine exits -- success,
exception, or cancellation -- use a `finally` block:

```python
# finally_cleanup.py
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

```text
$ python finally_cleanup.py
alpha: starting
alpha: cleaning up
Timed out
```

The `finally` block ran even though the coroutine was cancelled. Reach for
`try`/`finally` first; reserve `except CancelledError` for the rare cases
where cleanup is *specific* to cancellation (e.g., logging a different
message).

## `asyncio.timeout()`

[`asyncio.timeout()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout)
is an async context manager that enforces a deadline on the code inside it. If
the block takes longer than the specified number of seconds, asyncio cancels
the current task and converts the resulting `CancelledError` into a
[`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError)
at the `async with` boundary.

```python
# timeout_basic.py
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

```text
$ python timeout_basic.py
Operation timed out after 1 second
```

There are two important things to understand here. First,
`asyncio.timeout()` cancels the *current task*. The `CancelledError` is raised
at whatever `await` the task is suspended on. Second, the conversion from
`CancelledError` to `TimeoutError` only happens at the `async with` boundary.
If your code receives a `CancelledError` from *outside* the timeout scope
(e.g., a parent `TaskGroup` shutting down), that cancellation passes through
unchanged -- it does not become a `TimeoutError`.

You can pass `None` as the delay to create a timeout that never fires -- useful
when the timeout value comes from configuration and `None` means "no limit":

```python
delay: float | None = None  # From config
async with asyncio.timeout(delay):
    await slow_operation()
```

> [!TIP]
> **Trio users:** `asyncio.timeout()` is equivalent to
> `trio.fail_after()`. The main difference is that Trio uses *cancel scopes*
> as an explicit concept, while asyncio's timeout context managers handle the
> scoping implicitly.

## `asyncio.timeout_at()`

[`asyncio.timeout_at()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout_at)
works like `asyncio.timeout()` but takes an *absolute* deadline based on the
event loop's internal clock, rather than a relative delay.

> [!NOTE]
> `asyncio.get_running_loop()` is covered in
> [Chapter 4](../04-the-low-level-toolkit/loop-access-and-inspection.md).
> Here you use it only to read the event-loop clock for `timeout_at()`.

```python
# timeout_at_demo.py
import asyncio

async def main() -> None:
    loop_time: float = asyncio.get_running_loop().time()
    deadline: float = loop_time + 2.0  # 2 seconds from now

    try:
        async with asyncio.timeout_at(deadline):
            print(f"Deadline set at loop time {deadline:.1f}")
            await asyncio.sleep(10)
    except TimeoutError:
        elapsed: float = asyncio.get_running_loop().time() - loop_time
        print(f"Timed out after {elapsed:.1f}s")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python timeout_at_demo.py
Deadline set at loop time 2.0
Timed out after 2.0s
```

Absolute deadlines are useful when you have a top-level time budget and want
to pass the remaining time down through multiple operations. Like
`asyncio.timeout()`, passing `None` disables the timeout.

## Checking Whether a Timeout Fired

The context manager returned by `asyncio.timeout()` and `asyncio.timeout_at()`
has an
[`expired()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.Timeout.expired)
method that tells you whether the timeout actually fired. This is useful when
you want to attempt something optimistically and take a different path if it
was too slow:

```python
# timeout_expired.py
import asyncio

async def try_fast_path() -> str | None:
    cm = asyncio.timeout(0.5)
    async with cm:
        await asyncio.sleep(2)  # Too slow
        return "fast result"

    # We get here only if the block exited (normally or via TimeoutError)
    if cm.expired():
        return None
    return "fast result"

async def main() -> None:
    result: str | None = await try_fast_path()
    if result is None:
        print("Fast path timed out, using slow fallback")
    else:
        print(f"Got: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python timeout_expired.py
Fast path timed out, using slow fallback
```

When the timeout fires, the `async with` block exits via `TimeoutError`.
The context manager handles it internally, so execution continues after the
block. You then check `cm.expired()` to decide what to do next.

> [!IMPORTANT]
> The code *after* the `async with` block runs only if the timeout fired or
> the block completed normally. If the task is cancelled for a reason *other*
> than this timeout, the `CancelledError` propagates out without reaching the
> code after the block.

## Timeouts and TaskGroups

Timeouts and `TaskGroup`s work together in two natural patterns.

**Pattern 1: Timeout around a TaskGroup.** The entire group must finish within
the deadline. When the timeout fires, it cancels the current task, which
triggers the `TaskGroup` to cancel all its children:

```python
# timeout_around_group.py
import asyncio

async def fetch(url: str) -> str:
    await asyncio.sleep(2)
    return f"Data from {url}"

async def main() -> None:
    try:
        async with asyncio.timeout(1):
            async with asyncio.TaskGroup() as tg:
                tg.create_task(fetch("https://example.com/a"))
                tg.create_task(fetch("https://example.com/b"))
                tg.create_task(fetch("https://example.com/c"))
    except TimeoutError:
        print("All fetches cancelled -- group took too long")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python timeout_around_group.py
All fetches cancelled -- group took too long
```

The timeout fires after one second, cancelling the host task. The `TaskGroup`
sees the cancellation and cancels all three children. Clean and predictable.

**Pattern 2: Individual timeouts inside TaskGroup children.** Each child
manages its own deadline independently:

```python
# timeout_inside_group.py
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
        t1 = tg.create_task(fetch_with_timeout("https://example.com/fast", 3.0))
        t2 = tg.create_task(fetch_with_timeout("https://example.com/slow", 0.5))

    print(t1.result())
    print(t2.result())

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python timeout_inside_group.py
Data from https://example.com/fast
TIMEOUT for https://example.com/slow
```

Here the second task timed out, but it handled the `TimeoutError` internally.
Since it didn't *raise*, the `TaskGroup` didn't cancel the first task. Choose
based on whether the timeout is a property of the whole group or of individual
operations.

> [!WARNING]
> If a child task's timeout raises `TimeoutError` and that error is *not*
> caught inside the child, it propagates into the `TaskGroup`, which treats it
> as a child failure and cancels all siblings. Make sure individual timeouts
> are handled within the child if you want the group to continue.

## The `except BaseException:` Trap

Because `CancelledError` inherits from `BaseException`, a bare `except:` or
`except BaseException:` will catch it. This is almost never what you want.

```python
# bare_except_broken.py — DO NOT DO THIS
import asyncio

async def bad_handler() -> None:
    try:
        await asyncio.sleep(10)
    except BaseException:
        print("Caught something, ignoring it")  # Swallows CancelledError!

async def main() -> None:
    try:
        async with asyncio.timeout(0.5):
            await bad_handler()
    except TimeoutError:
        print("Timed out")

if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python bare_except_broken.py
Caught something, ignoring it
```

The timeout never fires as far as the caller is concerned -- `bad_handler`
swallowed the `CancelledError`. The `TimeoutError` never appears.

If you genuinely need `except BaseException:` (for logging, metrics, or
similar cross-cutting concerns), always re-raise:

```python
async def safe_handler() -> None:
    try:
        await asyncio.sleep(10)
    except BaseException:
        print("Caught something, re-raising")
        raise  # Critical: let CancelledError propagate
```

The safe rule of thumb: use `except Exception:` for error handling -- it
naturally lets `CancelledError` and `KeyboardInterrupt` pass through. Reach
for `except BaseException:` only when you have a specific reason, and always
re-raise at the end.

> [!TIP]
> A quick way to audit your codebase: search for `except BaseException` and
> bare `except:` statements. Every match should either re-raise the caught
> exception or have a very good comment explaining why it doesn't.

---

That covers cancellation and timeouts -- the mechanisms that give your async
code real deadlines and real cleanup. Next up:
[Resource Management](resource-management.md), where you will learn how
`async with`, `try`/`finally`, and async generators work together to manage
resources that need asynchronous teardown.
