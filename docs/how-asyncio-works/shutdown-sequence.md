---
title: Shutdown Sequence
description: >-
  What asyncio.run() does when your main coroutine returns — pending task
  cancellation, async generator shutdown, executor shutdown, and loop
  closure. Understand the warnings and tracebacks that appear during
  shutdown.
---

# Shutdown Sequence

Your `#!py main()` coroutine returns, and you might think the program is done. It is
not -- at least, not yet.
[`asyncio.run()`][asyncio-run]
has a careful shutdown sequence to run before the process can exit cleanly. It
needs to cancel any tasks you left behind, finalize async generators that were
never fully iterated, drain the thread pool, and close the event loop. If you
understand this sequence, the warnings and tracebacks that appear during
shutdown stop being mysterious.

## The [`asyncio.run()`][asyncio-run] Shutdown Sequence

When your top-level coroutine finishes -- whether it returns normally or raises
an exception -- [`asyncio.run()`][asyncio-run] does not simply close the loop. It walks
through a deliberate multi-step teardown:

1. **Your main coroutine completes.** It returns a value or raises an
   exception. [`asyncio.run()`][asyncio-run] stores the result (or exception) for later.

2. **Collect all pending tasks.** [`asyncio.run()`][asyncio-run] calls
   [`asyncio.all_tasks()`][asyncio-all-tasks]
   to find every task still attached to the loop. Any task that has not
   finished -- still waiting on I/O, sleeping, or simply never awaited -- shows
   up here.

3. **Cancel every pending task.** Each task in that set gets a
   [`task.cancel()`][task-cancel]
   call. This schedules a [`CancelledError`][cancellederror] to be thrown into the coroutine at
   its next checkpoint.

4. **Run the loop until all cancelled tasks are done.** [`asyncio.run()`][asyncio-run] calls
   `#!py loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))`
   so that every cancelled task gets a chance to run its `finally` blocks and
   `__aexit__` methods. This is why cleanup code in cancelled tasks actually
   executes -- the loop keeps spinning long enough for the cancellation to
   unwind.

5. **Shut down async generators.** The loop calls
   [`loop.shutdown_asyncgens()`][loop-shutdown-asyncgens],
   which finalizes any async generators that were abandoned without being
   iterated to completion or explicitly closed.

6. **Shut down the default executor.** The loop calls
   [`loop.shutdown_default_executor()`][loop-shutdown-default-executor],
   which waits for any threads still running from
   [`asyncio.to_thread()`][asyncio-to-thread]
   or
   [`loop.run_in_executor()`][loop-run-in-executor]
   to finish.

7. **Close the loop.**
   [`loop.close()`][loop-close]
   releases all resources associated with the event loop. After this, the loop
   cannot be used again.

Only after all seven steps complete does [`asyncio.run()`][asyncio-run] return (or re-raise)
the result from step 1.

!!! note

    Steps 5 and 6 were added in Python 3.9 and 3.12 respectively, but if
    you are on Python 3.11+ (which this guide assumes), both are part of
    the standard shutdown. You do not need to call them yourself --
    [`asyncio.run()`][asyncio-run] handles everything.

## Leaked Tasks

The most common shutdown surprise comes from *leaked tasks* -- tasks you
created with [`asyncio.create_task()`][asyncio-create-task] but never awaited. When `#!py main()` returns,
those tasks are still pending. [`asyncio.run()`][asyncio-run] cancels them at step 3, and
they typically get cleaned up. But you will see a warning like this in the
logs:

```python title="leaked_task.py"
import asyncio

async def background_worker() -> None:
    while True:
        await asyncio.sleep(1)
        print("working...")

async def main() -> None:
    asyncio.create_task(background_worker())  # No reference, never awaited
    await asyncio.sleep(2.5)
    print("main() is done")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python leaked_task.py"
working...
working...
main() is done
```

The task runs in the background for a while, then `#!py main()` returns and
[`asyncio.run()`][asyncio-run] cancels it during shutdown. In debug mode (or depending on
garbage collection timing), you may see:

```text
Task was destroyed but it is pending!
task: <Task pending name='Task-2' coro=<background_worker() ...>>
```

This warning tells you that a task existed at the time the loop was closing
and had to be forcibly cleaned up. It is not always fatal, but it signals a
structural problem: somewhere in your code, a task's lifetime was not tied to a
scope.

!!! warning

    The "Task was destroyed but it is pending" warning means you have an
    ownership gap. A task was created but nobody was responsible for
    awaiting it. Even though [`asyncio.run()`][asyncio-run] cancels these tasks, the
    warning is telling you that your program's concurrency structure has a
    hole.

### Why [`TaskGroup`][taskgroup] Prevents This

A [`TaskGroup`][taskgroup] is the fix. Every
task created with `#!py tg.create_task()` is awaited
before the `#!py async with` block exits. There is no way for a task to leak out
of the group:

```python
async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(background_worker())
        await asyncio.sleep(2.5)
    # All tasks are done (or cancelled) before we get here
```

When the `#!py async with` block exits, the [`TaskGroup`][taskgroup] cancels any children that
are still running and waits for them. By the time `#!py main()` returns, there are
no orphan tasks for [`asyncio.run()`][asyncio-run] to clean up. No warnings, no surprises.

## Async Generator Finalization

Async generators that are abandoned -- iterated partially and then forgotten --
pose a cleanup problem. Their `finally` blocks may hold resources that need
async teardown, but the generator is no longer being driven by anything.

At step 5 of the shutdown sequence, [`asyncio.run()`][asyncio-run] calls
[`loop.shutdown_asyncgens()`][loop-shutdown-asyncgens] to finalize any generators that are still alive.
This triggers their `finally` blocks and [`aclose()`][aclose] methods, giving them a
last chance to release resources.

```python title="abandoned_agen.py"
import asyncio
from collections.abc import AsyncIterator

async def ticker() -> AsyncIterator[int]:
    n = 0
    try:
        while True:
            await asyncio.sleep(0.5)
            n += 1
            yield n
    finally:
        print(f"ticker: finalized after yielding {n} values")

async def main() -> None:
    agen = ticker()
    print(await agen.__anext__())
    print(await agen.__anext__())
    # Abandon the generator -- never call aclose()

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python abandoned_agen.py"
1
2
ticker: finalized after yielding 2 values
```

The generator's `finally` block ran during shutdown, thanks to
`#!py shutdown_asyncgens()`. But relying on this is fragile -- it only runs during
[`asyncio.run()`][asyncio-run] teardown, so if you are using a custom loop setup or the
generator holds a resource that should be released *before* shutdown, it will
be too late.

The right approach is the one covered in
[Resource Management](../the-basics/resource-management.md): wrap
every async generator you consume in
[`contextlib.aclosing()`][contextlib-aclosing]
so it is closed deterministically when you are done with it, not at some
later point during shutdown.

!!! tip

    Think of `#!py shutdown_asyncgens()` as a safety net, not a strategy. Use
    `#!py aclosing()` so your generators are cleaned up at the right time, not
    just at the last possible moment.

## Executor Shutdown

If your program used
[`asyncio.to_thread()`][asyncio-to-thread]
or
[`loop.run_in_executor()`][loop-run-in-executor]
to offload blocking work, the default [`ThreadPoolExecutor`][threadpoolexecutor] may still have
threads running when `#!py main()` returns. Step 6 of the shutdown sequence calls
[`loop.shutdown_default_executor()`][loop-shutdown-default-executor], which signals the executor to stop
accepting new work and then waits for all in-flight threads to complete.

This is usually invisible -- your blocking functions finish, the threads join,
and the loop closes. It becomes noticeable only if one of those threads is
stuck in a long-running or hanging call, in which case shutdown will block
waiting for it. There is not much you can do about that from the asyncio side;
the solution is to fix the blocking code so it respects timeouts or can be
interrupted.

## Clean Shutdown Patterns

If you followed the advice from Chapter 1, clean shutdown is largely
automatic. Here is a summary of the patterns that make it work:

**Use [`TaskGroup`][taskgroup] for all concurrency.** Every task is tied to a scope and
awaited before that scope exits. No leaked tasks, no warnings.

```python
async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(worker_a())
        tg.create_task(worker_b())
    # Both tasks guaranteed done here
```

**Use `#!py async with` for resources.** Connections, locks, sessions -- anything
that needs cleanup gets an `#!py async with` block. Cleanup runs on normal exit,
on exception, and on cancellation.

```python
async def main() -> None:
    async with SomeConnection() as conn:
        await conn.do_work()
    # Connection closed, regardless of how the block exited
```

**Use `#!py aclosing()` for async generators.** Generators are closed
deterministically when the `#!py async with` block exits, not deferred to shutdown.

```python
from contextlib import aclosing

async def main() -> None:
    async with aclosing(some_async_generator()) as items:
        async for item in items:
            process(item)
    # Generator finalized immediately
```

If you combine all three, your `#!py main()` coroutine returns with nothing left to
clean up. [`asyncio.run()`][asyncio-run] still runs its full shutdown sequence, but steps 2
through 5 find nothing to do -- every task is already done, every generator
already closed, every resource already released. That is the ideal.

!!! info

    Clean shutdown is not about adding shutdown *code*. It is about
    structuring your program so that lifetimes are explicit and scoped. If
    you find yourself writing manual shutdown logic -- collecting tasks,
    cancelling them one by one, catching stray exceptions -- step back and
    ask whether the tasks should have been in a [`TaskGroup`][taskgroup] to begin with.

## Signal Handling

In long-running programs like servers, shutdown is not triggered by `#!py main()`
returning -- it is triggered by a signal like `SIGINT` (Ctrl+C) or `SIGTERM`.
The event loop provides
[`loop.add_signal_handler()`][loop-add-signal-handler]
for registering callbacks that respond to these signals, allowing you to
initiate a graceful shutdown -- cancelling a sentinel event, setting a flag, or
cancelling the main task -- instead of just crashing.

Signal handling is a lower-level topic that belongs in
[The Low-Level Toolkit](../the-low-level-toolkit/index.md). For now, the
important thing to know is that the shutdown *sequence* described above is the
same regardless of what triggered it. Whether `#!py main()` returns on its own or
you cancel the main task in response to a signal, [`asyncio.run()`][asyncio-run] still walks
through the same seven steps.

---

[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[asyncio-all-tasks]: https://docs.python.org/3/library/asyncio-task.html#asyncio.all_tasks
[task-cancel]: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[loop-shutdown-asyncgens]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.shutdown_asyncgens
[loop-shutdown-default-executor]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.shutdown_default_executor
[asyncio-to-thread]: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
[loop-run-in-executor]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor
[loop-close]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.close
[asyncio-create-task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[aclose]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack.aclose
[contextlib-aclosing]: https://docs.python.org/3/library/contextlib.html#contextlib.aclosing
[threadpoolexecutor]: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor
[loop-add-signal-handler]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.add_signal_handler