# Task Coordination

Previous: [Loop Access and Inspection](loop-access-and-inspection.md)
Next: [Futures](futures.md)

`TaskGroup` is the right default for concurrent work -- it owns every child,
cancels siblings on failure, and guarantees that nothing outlives the scope.
But its contract is strict: *all* tasks must complete (or fail) before the
group exits. Sometimes that is not what you need. You might want to act on
whichever task finishes first, process results in completion order, or enforce
a timeout on a single awaitable at an API boundary. That is what
`asyncio.wait()`, `asyncio.as_completed()`, and `asyncio.wait_for()` are for.

> [!CAUTION]
> Everything in this section bypasses structured concurrency. These APIs do not
> own the tasks they operate on -- they do not cancel stragglers, propagate
> exceptions, or guarantee cleanup. You are responsible for all of that. Prefer
> `TaskGroup` for application code. Reach for these tools in library code,
> protocol implementations, and the specific situations described at the end of
> this section.

## `asyncio.wait()`

[`asyncio.wait()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait)
takes an iterable of tasks (or other awaitables wrapped in tasks) and returns
two sets: `done` and `pending`. The `return_when` parameter controls when it
returns.

The signature (simplified):

```python
async def wait(
    fs: Iterable[asyncio.Task[T]],
    *,
    timeout: float | None = None,
    return_when: str = asyncio.ALL_COMPLETED,
) -> tuple[set[asyncio.Task[T]], set[asyncio.Task[T]]]:
    ...
```

There are three modes.

### `ALL_COMPLETED` -- wait for everything

This is the default. `wait()` returns when every task in the set has finished.
It is similar to what `TaskGroup` does, but without sibling cancellation or
exception propagation -- you get back two sets and must inspect them yourself.

```python
# wait_all_completed.py
import asyncio


async def job(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return f"{name} done"


async def main() -> None:
    tasks: set[asyncio.Task[str]] = {
        asyncio.create_task(job("alpha", 0.3), name="alpha"),
        asyncio.create_task(job("beta", 0.1), name="beta"),
        asyncio.create_task(job("gamma", 0.2), name="gamma"),
    }

    done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    print(f"done: {len(done)}, pending: {len(pending)}")
    for t in done:
        print(f"  {t.get_name()} -> {t.result()}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python wait_all_completed.py
done: 3, pending: 0
  alpha -> alpha done
  beta -> beta done
  gamma -> gamma done
```

### `FIRST_COMPLETED` -- return as soon as any task finishes

This is the most useful mode. It lets you react to whichever task finishes
first -- perfect for racing multiple strategies or draining a dynamic pool.

```python
# wait_first_completed.py
import asyncio
import random


async def fetch_mirror(mirror: str) -> str:
    delay: float = random.uniform(0.1, 1.0)
    await asyncio.sleep(delay)
    return f"data from {mirror} ({delay:.2f}s)"


async def main() -> None:
    mirrors: list[str] = ["mirror-a", "mirror-b", "mirror-c"]
    tasks: set[asyncio.Task[str]] = {
        asyncio.create_task(fetch_mirror(m), name=m) for m in mirrors
    }

    # Take the first result, cancel the rest
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    winner: asyncio.Task[str] = done.pop()
    print(f"Winner: {winner.result()}")

    # CRITICAL: cancel the stragglers yourself
    for t in pending:
        t.cancel()
    # Wait for cancellations to propagate
    await asyncio.wait(pending)

    print(f"Cancelled {len(pending)} remaining tasks")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python wait_first_completed.py
Winner: data from mirror-b (0.14s)
Cancelled 2 remaining tasks
```

### `FIRST_EXCEPTION` -- return when any task raises

`FIRST_EXCEPTION` returns as soon as a task raises an exception. If no task
raises, it behaves like `ALL_COMPLETED`. The failed task ends up in the `done`
set -- call `.exception()` on it to see what happened.

```python
# wait_first_exception.py
import asyncio


async def healthy_worker(name: str) -> str:
    await asyncio.sleep(1.0)
    return f"{name} ok"


async def flaky_worker() -> str:
    await asyncio.sleep(0.2)
    raise ConnectionError("lost connection")


async def main() -> None:
    tasks: set[asyncio.Task[str]] = {
        asyncio.create_task(healthy_worker("w1"), name="w1"),
        asyncio.create_task(healthy_worker("w2"), name="w2"),
        asyncio.create_task(flaky_worker(), name="flaky"),
    }

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

    for t in done:
        if t.exception() is not None:
            print(f"{t.get_name()} failed: {t.exception()}")
        else:
            print(f"{t.get_name()} succeeded: {t.result()}")

    print(f"{len(pending)} tasks still running")

    # Clean up pending tasks
    for t in pending:
        t.cancel()
    await asyncio.wait(pending)


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python wait_first_exception.py
flaky failed: lost connection
2 tasks still running
```

### The critical footgun: `wait()` does NOT cancel pending tasks

This is worth repeating in its own callout because it is the single most
common mistake with `asyncio.wait()`:

> [!WARNING]
> **`asyncio.wait()` never cancels anything.** When it returns, the tasks in
> the `pending` set are still running. If you do not cancel them yourself, they
> will keep running in the background with no owner -- exactly the fire-and-
> forget problem that `TaskGroup` was designed to prevent.

The safe pattern is always the same: wait, cancel pending, wait again.

```python
done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

# Process done tasks...

# Then clean up:
for t in pending:
    t.cancel()
# Give the cancelled tasks a chance to run their finally blocks
if pending:
    await asyncio.wait(pending)
```

The second `await asyncio.wait(pending)` is not optional. Calling `t.cancel()`
only *requests* cancellation -- the `CancelledError` is delivered at the next
checkpoint. Without the second wait, the cancelled tasks may not have finished
their cleanup before your code moves on.

### `timeout` parameter

`asyncio.wait()` accepts an optional `timeout` in seconds. If the timeout
expires before the `return_when` condition is met, `wait()` returns with
whatever has completed so far in `done` and the rest in `pending`. No tasks
are cancelled -- the timeout just controls how long `wait()` itself blocks.

```python
done, pending = await asyncio.wait(tasks, timeout=2.0)
# If 2s passed before all tasks finished, pending is non-empty
```

## `asyncio.as_completed()`

[`asyncio.as_completed()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.as_completed)
is for when you want to process results in the order they arrive, not the
order you submitted them. It takes an iterable of awaitables and returns an
*asynchronous iterator* of futures that yield results in completion order.

```python
# as_completed_demo.py
import asyncio
import random


async def fetch(url: str) -> str:
    delay: float = random.uniform(0.1, 1.0)
    await asyncio.sleep(delay)
    return f"{url}: {delay:.2f}s"


async def main() -> None:
    urls: list[str] = [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
        "https://example.com/d",
    ]

    coros = [fetch(url) for url in urls]

    for future in asyncio.as_completed(coros):
        result: str = await future
        print(f"Got: {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python as_completed_demo.py
Got: https://example.com/c: 0.12s
Got: https://example.com/a: 0.34s
Got: https://example.com/d: 0.51s
Got: https://example.com/b: 0.87s
```

The order changes every run because it depends on the random delays. The point
is that you process the *fastest* result first, without waiting for all of
them.

A few things to note:

- `as_completed()` accepts coroutines directly -- it wraps them in tasks
  internally. You can also pass `Task` objects.
- The iterator yields `Future` objects, not `Task` objects. You `await` each
  one to get the result (or raise the exception).
- Like `wait()`, there is an optional `timeout` parameter. If the timeout
  expires, the next `await future` in the loop raises `TimeoutError`.

### Practical use case: logging progress

`as_completed()` is ideal when you want to report progress as work completes:

```python
# as_completed_progress.py
import asyncio
import random


async def download(file_id: int) -> int:
    size: int = random.randint(100, 1000)
    await asyncio.sleep(size / 1000)  # Simulate download time proportional to size
    return size


async def main() -> None:
    total_files: int = 6
    coros = [download(i) for i in range(total_files)]

    completed: int = 0
    total_bytes: int = 0

    for future in asyncio.as_completed(coros):
        size: int = await future
        completed += 1
        total_bytes += size
        print(f"[{completed}/{total_files}] Downloaded {size} bytes "
              f"(total: {total_bytes})")

    print(f"\nAll done: {total_bytes} bytes from {total_files} files")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python as_completed_progress.py
[1/6] Downloaded 142 bytes (total: 142)
[2/6] Downloaded 271 bytes (total: 413)
[3/6] Downloaded 389 bytes (total: 802)
[4/6] Downloaded 534 bytes (total: 1336)
[5/6] Downloaded 712 bytes (total: 2048)
[6/6] Downloaded 918 bytes (total: 2966)

All done: 2966 bytes from 6 files
```

## `asyncio.wait_for()`

[`asyncio.wait_for()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for)
wraps a single awaitable with a timeout. If the timeout expires, it *cancels*
the awaitable and raises
[`TimeoutError`](https://docs.python.org/3/library/exceptions.html#TimeoutError).

```python
# wait_for_demo.py
import asyncio


async def slow_query(query: str) -> str:
    await asyncio.sleep(5.0)
    return f"Results for: {query}"


async def main() -> None:
    try:
        result: str = await asyncio.wait_for(slow_query("SELECT *"), timeout=1.0)
        print(result)
    except TimeoutError:
        print("Query timed out after 1 second")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python wait_for_demo.py
Query timed out after 1 second
```

### `wait_for()` vs `asyncio.timeout()`

Chapter 1 covered
[`asyncio.timeout()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout),
the context manager that enforces a deadline on a block of code. Both
`wait_for()` and `timeout()` cancel work that takes too long, but they have
different shapes and different trade-offs.

| | `asyncio.timeout()` | `asyncio.wait_for()` |
|---|---|---|
| **Scope** | A block of code (multiple awaits) | A single awaitable |
| **Syntax** | `async with asyncio.timeout(n):` | `await asyncio.wait_for(coro, timeout=n)` |
| **Cancels** | The current task at the next checkpoint | The wrapped awaitable specifically |
| **Raises** | `TimeoutError` at the `async with` boundary | `TimeoutError` at the `await` |
| **Added** | Python 3.11 | Python 3.0+ (older API) |

For application code, prefer `asyncio.timeout()`. It works on blocks, composes
with `TaskGroup`, and has clear scoping. `wait_for()` is useful at API
boundaries where you are wrapping a single coroutine call and want a concise
one-liner -- particularly in library code where you do not control what the
caller does before or after.

### The suppressed-cancellation gotcha

`wait_for()` has a subtle edge case. When the timeout fires, `wait_for()`
cancels the wrapped task and waits for it to finish. If the wrapped coroutine
catches `CancelledError` and *suppresses* it (returns a value instead of
re-raising), `wait_for()` may return that value instead of raising
`TimeoutError`. Your code thinks the operation succeeded when it actually
timed out.

```python
# wait_for_gotcha.py
import asyncio


async def sneaky_coroutine() -> str:
    try:
        await asyncio.sleep(10)
        return "normal result"
    except asyncio.CancelledError:
        # BUG: suppresses cancellation
        return "fallback result"


async def main() -> None:
    try:
        result: str = await asyncio.wait_for(sneaky_coroutine(), timeout=0.5)
        # This may print "fallback result" instead of raising TimeoutError!
        print(f"Got: {result}")
    except TimeoutError:
        print("Timed out")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python wait_for_gotcha.py
Got: fallback result
```

The coroutine swallowed `CancelledError` and returned a string. `wait_for()`
saw the task complete "successfully" and returned the result. This is
another reason to never suppress `CancelledError` -- the
[Cancellation and Timeouts](../everyday-asyncio/cancellation-and-timeouts.md)
section in Chapter 1 explains this rule in detail.

> [!NOTE]
> `asyncio.timeout()` does not have this problem. It cancels the *current
> task*, so the `CancelledError` propagates through the entire call chain.
> The context manager then converts it to `TimeoutError` at the `async with`
> boundary. There is no intermediate task whose completion state can hide the
> cancellation.

### Passing `timeout=None`

Like `asyncio.timeout()`, passing `None` as the timeout disables it entirely.
This is useful when the timeout value comes from configuration:

```python
deadline: float | None = config.get("query_timeout")  # might be None
result = await asyncio.wait_for(slow_query("SELECT *"), timeout=deadline)
```

## When to Use These Instead of `TaskGroup`

Use `TaskGroup` by default. Reach for the tools in this section only when
`TaskGroup`'s all-or-nothing contract does not fit your problem.

Here is a quick decision guide:

**Partial completion.** You need the first result and want to abandon the rest.
A redundant-request pattern (try multiple mirrors, use the fastest) is a
classic example.

  Use `asyncio.wait(tasks, return_when=FIRST_COMPLETED)`.

**Processing in completion order.** You have N tasks and want to process each
result as it arrives, not in submission order. Progress reporting, streaming
responses to a client, or feeding results into a pipeline all fit this pattern.

  Use `asyncio.as_completed(coros)`.

**Single-coroutine timeout at an API boundary.** You are writing a library
function that wraps exactly one awaitable and needs to enforce a deadline
without requiring the caller to set up a context manager.

  Use `asyncio.wait_for(coro, timeout=n)`.

**Dynamic task sets.** You have a long-lived loop that adds and removes tasks
over time -- a connection pool, a task scheduler, a supervisor. `TaskGroup`
expects a fixed scope; `wait()` with `FIRST_COMPLETED` lets you run a
continuous select-loop over a changing set of tasks.

  Use `asyncio.wait()` in a loop, adding new tasks and removing done ones
  each iteration.

**Everything else.** Bounded concurrent work where all tasks must succeed or
the group fails? That is `TaskGroup`.

> [!TIP]
> If you find yourself reaching for `wait()` or `as_completed()` in
> application code, ask yourself: "Am I doing this because `TaskGroup` cannot
> express this pattern, or because I did not know `TaskGroup` could?" Nine
> times out of ten, `TaskGroup` is the better choice. The tenth time, these
> tools are indispensable.

---

That covers the low-level task coordination APIs -- the tools you reach for
when `TaskGroup`'s structured contract is too rigid. Next up:
[Futures](futures.md), where you will work with `asyncio.Future` directly,
bridge `concurrent.futures`, and see how manual result resolution works under
the hood.
