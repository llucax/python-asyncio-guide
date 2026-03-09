---
title: Concurrent Tasks
description: >-
  Master structured concurrency with asyncio.TaskGroup. Learn to run tasks
  concurrently, handle ExceptionGroups with except*, and understand why
  TaskGroup replaces fire-and-forget create_task().
---

# Concurrent Tasks

This is where asyncio gets interesting. Everything in the previous section was
sequential -- one coroutine, one [`await`][await] at a time, no overlap. The
whole reason you reached for asyncio is to do multiple things at once. This
section introduces *structured concurrency* with
[`asyncio.TaskGroup`][asyncio-taskgroup], the safe, modern way to run
concurrent tasks.

## What is a Task?

As seen in the [previous section](getting-started.md), a
[loop](getting-started.md#the-event-loop) is needed to *drive* coroutines. Each
corouting running independently needs some state to keep track of it --
whether it's done, its return value when it's done, if it ended with an
uncaught exception, etc. A *task* is a coroutine with its associated state.

## The Problem with Fire-and-Forget

Before [`TaskGroup`][taskgroup] existed, the way to launch concurrent work was
[`asyncio.create_task()`][asyncio-create-task].
It still exists, and you will see it in older code:

```python title="fire_and_forget.py"
import asyncio

async def fetch_data(url: str) -> str:
    await asyncio.sleep(1)
    if "bad" in url:
        raise ValueError(f"Failed to fetch {url}")
    return f"Data from {url}"

async def main() -> None:
    asyncio.create_task(fetch_data("https://example.com/good"))
    asyncio.create_task(fetch_data("https://example.com/bad"))
    await asyncio.sleep(0.5)
    print("main() is done!")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python fire_and_forget.py"
main() is done!
Task exception was never retrieved
  ...
ValueError: Failed to fetch https://example.com/bad
```

`#!py main()` finished after half a second, abandoning both tasks. The `ValueError`
went uncaught -- just a warning in the logs. This pattern has three problems:

1. **Lost references.** Without storing the [`Task`][task] object you cannot await it,
   check its result, or cancel it.
2. **Swallowed exceptions.** An orphaned task that raises produces a log
   warning, but your program keeps running as if nothing happened.
3. **Unclear lifetime.** When does the task finish? What happens when `#!py main()`
   returns? The answer is "it depends."

!!! tip

    **Forget that [`asyncio.create_task()`][asyncio-create-task] exists.** For
    the rest of this guide, you will never use it directly. Every task will be
    created inside a [`TaskGroup`][taskgroup], which solves all three problems
    above. If you see bare [`create_task()`][create-task] in a code review,
    treat it as a red flag.

## Structured Concurrency

The idea behind *structured concurrency* is simple: **every concurrent task has
an owner, and the owner cannot move on until all its tasks are done.** Just as
you don't use `goto` to jump out of a function, you don't launch tasks that
outlive their scope.

When you open a [`TaskGroup`][taskgroup], you create a scope. Tasks spawned
inside it are *children* of the group. The `#!py async with` block will not exit
until every child has finished -- whether successfully, by raising, or by being
cancelled. No orphans, no forgotten work, no swallowed errors.

!!! tip "Trio users"

    [`TaskGroup`][taskgroup] is asyncio's [nursery][trio-open-nursery].
    [`tg.create_task(coro)`][tg-create-task] is equivalent to
    [`nursery.start_soon(async_fn, *args)`][trio-start-soon], except it takes a
    coroutine object rather than a callable plus arguments.

## [`asyncio.TaskGroup`][asyncio-taskgroup]

Here is the basic pattern. Create a [`TaskGroup`][taskgroup] with `#!py async with`,
spawn tasks with [`tg.create_task()`][tg-create-task], and when the block ends
all tasks are guaranteed complete:

```python title="taskgroup_basic.py"
import asyncio

async def greet(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    message: str = f"Hello, {name}!"
    print(message)
    return message

async def main() -> None:
    async with asyncio.TaskGroup() as tg:  # (1)!
        tg.create_task(greet("Alice", 1.0))
        tg.create_task(greet("Bob", 0.5))
        print("Tasks are running...")

    # This line runs ONLY after both tasks have finished
    print("All greetings done.")

if __name__ == "__main__":
    asyncio.run(main())
```

1. The `#!py async with` block is the **ownership boundary**. Tasks spawned
   inside cannot outlive it -- the block will not exit until every child
   has finished, failed, or been cancelled.

```text title="$ python taskgroup_basic.py"
Tasks are running...
Hello, Bob!
Hello, Alice!
All greetings done.
```

Notice that Bob greets first because his delay is shorter -- both tasks ran
concurrently. The line after the `#!py async with` block only executes once *both*
tasks have completed. No orphans.

## Execution Trace

Here is exactly what happens inside the event loop, step by step:

1. `#!py asyncio.run(main())` creates the event loop and schedules `#!py main()`.
2. `#!py main()` runs. It enters the `#!py async with asyncio.TaskGroup() as tg:`
   block, creating a new task group.
3. `#!py tg.create_task(greet("Alice", 1.0))` puts Alice's coroutine on the
   ready queue as a task. `#!py tg.create_task(greet("Bob", 0.5))` does the
   same for Bob. Neither has started yet.
4. `#!py print("Tasks are running...")` executes -- this is synchronous code
   inside the `#!py async with` block, so it runs immediately.
5. Execution reaches the end of the `#!py async with` block. The [`TaskGroup`][taskgroup]
   now waits for all its children to complete. `#!py main()` suspends.
6. The loop picks Alice's task (first scheduled). Alice hits
   `#!py await asyncio.sleep(1.0)` and suspends -- the loop sets a 1-second
   timer.
7. The loop picks Bob's task. Bob hits `#!py await asyncio.sleep(0.5)` and
   suspends -- the loop sets a 0.5-second timer.
8. Both tasks are now waiting. The loop calls the OS to wait for the
   next timer.
9. After 0.5 seconds, Bob's timer fires. Bob resumes, prints
   `#!py "Hello, Bob!"`, returns, and his task is marked done.
10. After another 0.5 seconds (1.0 s total), Alice's timer fires. Alice
    resumes, prints `#!py "Hello, Alice!"`, returns, and her task is marked
    done.
11. All children are done, so the [`TaskGroup`][taskgroup] unblocks. `#!py main()` resumes
    and prints `#!py "All greetings done."`.
12. `#!py main()` returns and [`asyncio.run()`][asyncio-run] tears down the loop.

Nothing happens *at the same time*. Tasks take turns at [`await`][await] points
on a single thread. Bob finishes first because his timer is shorter, but
both tasks were on the loop's schedule simultaneously -- that is the
concurrency.

[`tg.create_task()`][tg-create-task] returns an [`asyncio.Task`][asyncio-task]
object. Store it if you need the return value (you will get to that shortly),
or ignore it if you only care about the side effects.

!!! info

    You can only call [`tg.create_task()`][tg-create-task] inside the `async
    with` block. Once the block is exiting (either normally or due to an
    exception), the group stops accepting new tasks.

## Sibling Cancellation

What happens when one child task fails? The [`TaskGroup`][taskgroup] cancels all surviving
siblings and raises the exception. This is *sibling cancellation*.

```python title="sibling_cancel.py" hl_lines="9"
import asyncio

async def fast_failure() -> None:
    await asyncio.sleep(0.1)
    raise RuntimeError("Something went wrong")

async def slow_worker() -> None:
    try:
        print("slow_worker: starting long operation...")
        await asyncio.sleep(10)
        print("slow_worker: finished!")  # Never reached
    except asyncio.CancelledError:
        print("slow_worker: I was cancelled!")
        raise  # Always re-raise CancelledError

async def main() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(slow_worker())
            tg.create_task(fast_failure())
    except* RuntimeError as eg:
        print(f"Caught errors: {eg.exceptions}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python sibling_cancel.py"
slow_worker: starting long operation...
slow_worker: I was cancelled!
Caught errors: (RuntimeError('Something went wrong'),)
```

The `fast_failure` task raised after 0.1 seconds. The [`TaskGroup`][taskgroup] cancelled
`slow_worker`, which caught [`CancelledError`][cancellederror] and re-raised (as it should --
never swallow [`CancelledError`][cancellederror]). Then the group wrapped the `RuntimeError` in
an [`ExceptionGroup`][exceptiongroup] and raised it.

The deep mechanics of cancellation -- [`CancelledError`][cancellederror] propagation, shielding,
timeouts -- belong in the [next section](cancellation-and-timeouts.md). For
now, remember: **if one child fails, the others don't keep running in the
dark.**

## [`ExceptionGroup`][exceptiongroup] and [`except*`][except]

You might have noticed the [`except*`][except] syntax above. When a [`TaskGroup`][taskgroup] has
failures, it raises an
[`ExceptionGroup`][exceptiongroup]
-- a container holding one or more exceptions from the failed children. This
is necessary because multiple children can fail simultaneously.

The
[`except*`][except] syntax
(introduced in [PEP 654](https://peps.python.org/pep-0654/)) lets you handle
specific exception types inside the group:

```python title="exception_group.py"
import asyncio

async def fail_value() -> None:
    await asyncio.sleep(0.1)
    raise ValueError("bad value")

async def fail_type() -> None:
    await asyncio.sleep(0.1)
    raise TypeError("wrong type")

async def fail_runtime() -> None:
    await asyncio.sleep(0.1)
    raise RuntimeError("runtime problem")

async def main() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(fail_value())
            tg.create_task(fail_type())
            tg.create_task(fail_runtime())
    except* ValueError as eg:
        for exc in eg.exceptions:
            print(f"Handled ValueError: {exc}")
    except* (TypeError, RuntimeError) as eg:
        for exc in eg.exceptions:
            print(f"Handled TypeError|RuntimeError: {exc}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python exception_group.py"
Handled ValueError: bad value
Handled TypeError|RuntimeError: wrong type
Handled TypeError|RuntimeError: runtime problem
```

A few things to note: multiple [`except*`][except] clauses can each match a *subset* of
the exceptions. Every exception gets routed to exactly one matching clause. If
any exceptions are *not* matched, they propagate upward as a new
[`ExceptionGroup`][exceptiongroup].

!!! warning

    You cannot mix `except` and [`except*`][except] in the same `try` block. If you use
    [`except*`][except], all handlers in that block must use the starred form. This is a
    syntax rule enforced by the Python interpreter.

!!! note

    If only a single child fails, the [`TaskGroup`][taskgroup] still wraps the exception in
    an [`ExceptionGroup`][exceptiongroup]. You always get a group, even if it contains just one
    item. This keeps the handling uniform.

## Collecting Results

In many cases you want return values from your concurrent tasks, not just side
effects. The pattern is straightforward: store the [`Task`][task] handles from
[`tg.create_task()`][tg-create-task], then call `#!py .result()` after the `#!py async with` block:

```python title="collect_results.py"
import asyncio

async def fetch_page(url: str) -> str:
    print(f"Fetching {url}...")
    await asyncio.sleep(0.5)  # Simulate network I/O
    return f"<html>Content of {url}</html>"

async def main() -> None:
    urls: list[str] = [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page3",
    ]

    async with asyncio.TaskGroup() as tg:
        tasks: list[asyncio.Task[str]] = [
            tg.create_task(fetch_page(url)) for url in urls
        ]

    # All tasks are done here -- safe to call .result()
    results: list[str] = [t.result() for t in tasks]
    for url, html in zip(urls, results):
        print(f"{url} -> {len(html)} chars")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python collect_results.py"
Fetching https://example.com/page1...
Fetching https://example.com/page2...
Fetching https://example.com/page3...
https://example.com/page1 -> 40 chars
https://example.com/page2 -> 40 chars
https://example.com/page3 -> 40 chars
```

All three fetches ran concurrently (total wall time ~0.5s, not ~1.5s). After
the `#!py async with` block, every task is guaranteed complete, so `#!py .result()`
returns immediately. If any task had failed, the [`TaskGroup`][taskgroup] would have raised
an [`ExceptionGroup`][exceptiongroup] before you ever reach the `#!py .result()` calls.

!!! tip

    You can also give tasks names for easier debugging:
    `#!py tg.create_task(fetch_page(url), name=f"fetch-{url}")`. The name shows up
    in logs and tracebacks.

## Nested TaskGroups

[`TaskGroup`][taskgroup]s can be nested, and each group is an independent scope. This is
useful when a piece of work is itself composed of concurrent sub-steps but
should be treated as a single unit from the parent's perspective.

```python title="nested_groups.py"
import asyncio

async def download(name: str) -> str:
    await asyncio.sleep(0.3)
    return f"{name}-data"

async def process_batch(batch_id: int, items: list[str]) -> list[str]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(download(item)) for item in items]
    results = [t.result() for t in tasks]
    print(f"Batch {batch_id}: {results}")
    return results

async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(process_batch(1, ["a", "b", "c"]))
        tg.create_task(process_batch(2, ["x", "y", "z"]))
    print("All batches complete.")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python nested_groups.py"
Batch 1: ['a-data', 'b-data', 'c-data']
Batch 2: ['x-data', 'y-data', 'z-data']
All batches complete.
```

The outer group owns two batch tasks. Each batch creates its own [`TaskGroup`][taskgroup]
for concurrent downloads. If a download in batch 1 fails, it cancels the
other downloads *in batch 1*. The failure then propagates to the outer group,
which cancels batch 2 -- sibling cancellation applies at every level.

## Practical Example: Fan-Out Workers

Let's put everything together. You have a list of jobs and you want to
spread them across several concurrent workers using a [`TaskGroup`][taskgroup]. The
simplest approach: slice the work up front and hand each worker its own
batch.

```python title="fan_out_workers.py"
import asyncio

async def worker(worker_id: int, jobs: list[str]) -> list[str]:
    results: list[str] = []
    for job in jobs:
        print(f"worker-{worker_id}: processing {job!r}")
        await asyncio.sleep(0.3)  # Simulate work
        results.append(f"{job}-done")
    return results

def distribute(items: list[str], n: int) -> list[list[str]]:
    """Split *items* into *n* roughly-equal chunks."""
    chunks: list[list[str]] = [[] for _ in range(n)]
    for i, item in enumerate(items):
        chunks[i % n].append(item)
    return chunks

async def main() -> None:
    n_workers: int = 3
    jobs: list[str] = ["alpha", "beta", "gamma", "delta", "epsilon"]
    batches: list[list[str]] = distribute(jobs, n_workers)

    async with asyncio.TaskGroup() as tg:
        worker_tasks: list[asyncio.Task[list[str]]] = [
            tg.create_task(worker(i, batch))
            for i, batch in enumerate(batches)
        ]

    all_results: list[str] = []
    for t in worker_tasks:
        all_results.extend(t.result())
    print(f"\nAll results: {all_results}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python fan_out_workers.py"
worker-0: processing 'alpha'
worker-1: processing 'beta'
worker-2: processing 'gamma'
worker-0: processing 'delta'
worker-1: processing 'epsilon'

All results: ['alpha-done', 'delta-done', 'beta-done', 'epsilon-done', 'gamma-done']
```

Each worker runs its batch concurrently with the others inside the
[`TaskGroup`][taskgroup]. If any worker raises, sibling cancellation kicks in -- the
group cancels the rest and propagates the error, exactly as you saw earlier.

!!! tip

    Pre-splitting works well when you know all jobs up front. For a dynamic
    pipeline where producers feed jobs to consumers at runtime -- with
    backpressure, shutdown signalling, and bounded queues -- see
    [Coordination](coordination.md#asyncioqueue).

## Mental Model: Two Questions

Now that you have seen checkpoints, task ownership, and sibling
cancellation in action, here is a mental model that ties it all together.
If you can answer two questions for any line of async code, most bugs
become obvious:

1. **Who owns the lifetime of this work?** Every task should have a
   clear owner -- something that will await it, cancel it, or handle
   its exceptions. With [`TaskGroup`][taskgroup], the answer is always "the group,"
   and the `#!py async with` block is the boundary.

2. **Where are the suspension points?** Every [`await`][await] is a place where
   your coroutine can pause and other tasks can run. Between two
   [`await`][await]s, you have exclusive access to your local state -- no other
   task can interleave.

Try applying them to code you have already seen. Look at
`#!py tg.create_task(fetch_page(url))`: who owns that task? The [`TaskGroup`][taskgroup].
Where can it suspend? At every [`await`][await] inside `fetch_page` -- in this
case, `#!py await asyncio.sleep(0.5)`. Between creating the task and the
next [`await`][await], no other task touches your variables.

Or look at the `worker` coroutine in the fan-out example: the code
between `#!py await asyncio.sleep(0.3)` and the next iteration of the loop
runs without interruption. You can safely append to `results` without
worrying about another worker modifying it -- each worker has its own
local list.

With [`TaskGroup`][taskgroup], the first question is always easy to answer. That is
the whole point of structured concurrency: ownership is visible in the
source code, not hidden in some global task registry.

Keep these two questions in the back of your mind as you read the rest
of the guide. They apply everywhere -- cancellation, timeouts, queues,
locks -- and they will save you from the most common async bugs.

---

[await]: https://docs.python.org/3/reference/expressions.html#await
[asyncio-taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[asyncio-create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task
[create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[asyncio-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[exceptiongroup]: https://docs.python.org/3/library/builtins.html#ExceptionGroup
[except]: https://docs.python.org/3/reference/compound_stmts.html#the-try-statement
[trio-open-nursery]: https://trio.readthedocs.io/en/stable/reference-core.html#trio.open_nursery
[trio-start-soon]: https://trio.readthedocs.io/en/stable/reference-core.html#trio.Nursery.start_soon
[tg-create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup.create_task
