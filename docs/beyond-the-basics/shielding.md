---
title: Shielding
description: >-
  Understand why a second cancellation can interrupt async cleanup, and
  learn how to use asyncio.shield() with an explicit owner to protect
  small, critical work without creating orphaned tasks.
---

# Shielding

Most of the time you should let cancellation propagate and use the
cleanup patterns from [Cancellation and
Timeouts](../the-basics/cancellation-and-timeouts.md). A `#!py finally`
block runs even when a task is cancelled, and for synchronous cleanup
that is all you need.

The trouble starts when cleanup itself must `#!py await` -- for example,
flushing file buffers, closing a stream cleanly, or committing a
transaction -- and a *second* cancellation arrives while that async
cleanup is in progress.

This section starts with the problem, explains how
[`asyncio.shield()`][asyncio-shield] addresses it, shows why using
[`asyncio.shield()`][asyncio-shield] without an owner is unsafe, and
then presents the recommended pattern.

## A Second Cancellation

Consider a file writer that flushes its buffers during teardown. The
write layer applies its own timeout, and `#!py main()` applies a
separate shutdown timeout above it:

```python title="file_write_double_cancel.py"
import asyncio
import time

T0 = time.monotonic()


def stamp() -> str:
    return f"{time.monotonic() - T0:.1f}s"


async def flush_file_buffers(path: str) -> None:
    print(f"flush: starting {path} at {stamp()}")
    await asyncio.sleep(2)
    print(f"flush: finished {path} at {stamp()}")


async def write_output_file(path: str) -> None:
    print(f"writer: starting {path} at {stamp()}")
    try:
        await asyncio.sleep(2)
        print(f"writer: finished {path} at {stamp()}")
    finally:
        await flush_file_buffers(path)


async def run_write_with_timeout(path: str) -> None:
    async with asyncio.timeout(1):
        await write_output_file(path)


async def run_batch_job(path: str) -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(run_write_with_timeout(path), name="write-output")
        print(f"batch: waiting for 5s at {stamp()}")
        await asyncio.sleep(5)


async def main() -> None:
    try:
        async with asyncio.timeout(1.5):
            await run_batch_job("report.txt")
    except TimeoutError:
        print(f"main: shutdown timeout at {stamp()}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python file_write_double_cancel.py"
batch: waiting for 5s at 0.0s
writer: starting report.txt at 0.0s
flush: starting report.txt at 1.0s
main: shutdown timeout at 1.5s
```

The `#!py finally` block lives in `#!py write_output_file()`, but the
two timeouts live in `#!py run_write_with_timeout()` and
`#!py main()`.
That is the normal shape in real programs: the code doing cleanup
usually does not control every cancellation scope above it.

Here is what happens step by step:

1. The write timeout in `#!py run_write_with_timeout()` fires at 1.0 s
   and cancels the writer task.
   [`CancelledError`][cancellederror] is raised at the
   `#!py await asyncio.sleep(2)` inside `#!py write_output_file()`.
2. The `#!py finally` block in `#!py write_output_file()` runs and
   starts `#!py flush_file_buffers(path)`. So far, so good -- the first
   cancellation
   has already been delivered, so the `#!py await asyncio.sleep(2)`
   inside `#!py flush_file_buffers(path)` proceeds normally.
3. The shutdown timeout in `#!py main()` fires at 1.5 s and delivers a
   *second* cancellation. This new
   [`CancelledError`][cancellederror] is raised at the
   `#!py await asyncio.sleep(2)` inside
   `#!py flush_file_buffers(path)`,
   interrupting the cleanup.
4. `#!py flush_file_buffers(path)` never finishes.

A single cancellation does not cause this problem. The first
[`CancelledError`][cancellederror] has already been delivered, and
subsequent `#!py await`s in `#!py finally` proceed normally. It is the
*second* cancellation -- from a parent [`TaskGroup`][taskgroup], an
outer timeout, or an explicit `#!py task.cancel()` call -- that
interrupts the cleanup.

This is the problem [`asyncio.shield()`][asyncio-shield] solves.

## `#!py asyncio.shield()`

[`asyncio.shield()`][asyncio-shield] takes an awaitable and returns a
wrapper. If the current task is cancelled while it is awaiting the
wrapper, the *inner* awaitable keeps running. The current task still
receives [`CancelledError`][cancellederror] at the `#!py await` --
shielding does not swallow cancellation.

If you pass a coroutine, [`asyncio.shield()`][asyncio-shield]
implicitly creates a task for it. If you pass an existing task or
future, it wraps that directly. In either case, cancelling the outer
wrapper severs the link between the two, and the inner work continues
independently.

If some other code cancels the inner task directly, shielding does not
stop that. [`asyncio.shield()`][asyncio-shield] only blocks
cancellation flowing *through* the `#!py await`.

## Why `#!py asyncio.shield(flush())` Alone Is Not Enough

A tempting first attempt is to wrap the cleanup call with
[`asyncio.shield()`][asyncio-shield]:

```python
finally:
    await asyncio.shield(flush_file_buffers(path))
```

This keeps the flush running when the second cancellation arrives, but
it has two problems:

1. **The flush task is orphaned.** Nobody holds a reference to it, nobody
    awaits its result, and nobody observes its exception. If the flush
    raises, the error is silently lost.
2. **Code after the shield does not run.** The
    [`CancelledError`][cancellederror] still propagates at the
    shielded `#!py await`, so the `#!py finally` block keeps unwinding.
    Any statements that follow are at the mercy of further cancellation
    pressure.

The flush *might* finish, but you have no way to know. You need an
owner.

## The Recommended Pattern

The fix is to create the cleanup task inside a longer-lived
[`TaskGroup`][taskgroup] and use [`asyncio.shield()`][asyncio-shield]
to try to wait for it in place. If a second cancellation interrupts the
shielded `#!py await`, the [`TaskGroup`][taskgroup] still owns the task
and will wait for it before exiting.

```python title="file_write_shield.py"
import asyncio
import time

T0 = time.monotonic()


def stamp() -> str:
    return f"{time.monotonic() - T0:.1f}s"


async def flush_file_buffers(path: str) -> None:
    print(f"flush: starting {path} at {stamp()}")
    await asyncio.sleep(2)
    print(f"flush: finished {path} at {stamp()}")


async def write_output_file(
    path: str,
    cleanup_tg: asyncio.TaskGroup,
) -> None:
    print(f"writer: starting {path} at {stamp()}")
    try:
        await asyncio.sleep(2)
        print(f"writer: finished {path} at {stamp()}")
    finally:
        flush_task: asyncio.Task[None] = cleanup_tg.create_task(
            flush_file_buffers(path),
            name="flush-report",
        )
        try:
            await asyncio.shield(flush_task)
        except asyncio.CancelledError:
            print(
                f"writer: shield cancelled, flush continues "
                f"under owner at {stamp()}"
            )
            raise


async def run_write_with_timeout(
    path: str,
    cleanup_tg: asyncio.TaskGroup,
) -> None:
    async with asyncio.timeout(1):
        await write_output_file(path, cleanup_tg)


async def run_batch_job(
    path: str,
    cleanup_tg: asyncio.TaskGroup,
) -> None:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(
            run_write_with_timeout(path, cleanup_tg),
            name="write-output",
        )
        print(f"batch: waiting for 5s at {stamp()}")
        await asyncio.sleep(5)


async def main() -> None:
    async with asyncio.TaskGroup() as cleanup_tg:
        try:
            async with asyncio.timeout(1.5):
                await run_batch_job("report.txt", cleanup_tg)
        except TimeoutError:
            print(f"main: shutdown timeout at {stamp()}")
    print(f"main: all cleanup done at {stamp()}")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python file_write_shield.py"
batch: waiting for 5s at 0.0s
writer: starting report.txt at 0.0s
flush: starting report.txt at 1.0s
writer: shield cancelled, flush continues under owner at 1.5s
main: shutdown timeout at 1.5s
flush: finished report.txt at 3.0s
main: all cleanup done at 3.0s
```

The key points:

- **The flush task is created under `#!py cleanup_tg`**, a
  [`TaskGroup`][taskgroup] that outlives the timeouts. That group will
  not exit its `#!py async with` block until the flush finishes.
- **`#!py asyncio.shield(flush_task)` tries to wait in place.** If no
  second cancellation arrives, the flush completes right there and the
  `#!py finally` block continues normally.
- **If the shield is cancelled**, the `#!py except CancelledError`
  catches the second delivery. The flush task is not affected -- it
  continues running under its owner.
- **Exceptions are observed.** If the flush raises, the
  [`TaskGroup`][taskgroup] surfaces the error as an
  [`ExceptionGroup`][exceptiongroup] when it exits.

!!! Tip

    Pass a task, not a bare coroutine, to
    [`asyncio.shield()`][asyncio-shield]. When you write `#!py
    asyncio.shield(some_coroutine())`, asyncio creates the task for you,
    but you do not keep your own handle to it. Creating the task yourself
    under a [`TaskGroup`][taskgroup] makes the ownership explicit.

!!! Note

    In the recommended pattern, the `#!py except CancelledError:` block
    logs what happened and immediately `#!py raise`s. That does not
    swallow cancellation. It only lets you observe the *second*
    delivery -- the one that interrupted the shielded wait -- before the
    [`CancelledError`][cancellederror] continues propagating.

## Structured Cleanup Without Shielding

In file-processing code, the cancelled task does not need to wait for
cleanup at all. It can hand the work off to a longer-lived
[`TaskGroup`][taskgroup] and exit immediately. No shielding is needed.

```python title="file_cleanup_taskgroup.py"
import asyncio


async def flush_file_buffers(path: str) -> None:
    print(f"flush: syncing {path}")
    await asyncio.sleep(0.5)
    print(f"flush: finished {path}")


async def write_output_file(
    path: str,
    cleanup_tg: asyncio.TaskGroup,
) -> None:
    try:
        print(f"writer: writing {path}")
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        cleanup_tg.create_task(
            flush_file_buffers(path),
            name="flush-report",
        )
        raise


async def main() -> None:
    async with asyncio.TaskGroup() as cleanup_tg:
        async with asyncio.TaskGroup() as writers:
            task: asyncio.Task[None] = writers.create_task(
                write_output_file("report.txt", cleanup_tg),
                name="write-report",
            )

            await asyncio.sleep(0.2)
            task.cancel()

        print("main: writer done, cleanup_tg still running")

    print("main: all cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python file_cleanup_taskgroup.py"
writer: writing report.txt
flush: syncing report.txt
main: writer done, cleanup_tg still running
flush: finished report.txt
main: all cleanup complete
```

The writer spawns the flush task into `#!py cleanup_tg` and re-raises
[`CancelledError`][cancellederror] immediately. The `#!py writers`
group finishes, but the `#!py cleanup_tg` group stays open until the
flush completes. Every task has an owner, and no shielding is involved.

When this design fits -- and it often does for batch jobs, background
writers, and file-processing pipelines -- prefer it over
[`asyncio.shield()`][asyncio-shield]. It is simpler and there is no
risk of accidentally orphaning work. Reserve shielding for cases where
the cancelled code itself needs to wait for the critical step before
continuing its own teardown.

!!! Tip "Trio"

    [Trio][trio-docs] does not have an equivalent of
    [`asyncio.shield()`][asyncio-shield]. Its
    [cancel scopes][trio-cancel-scopes] are strictly nested and cannot
    be "punched through." The Trio approach is to restructure the
    program so that the must-finish work lives in a scope that is not
    subject to the cancellation -- essentially the structured cleanup
    pattern shown above. If you find yourself reaching for shielding
    frequently, consider whether a restructure would be cleaner.

## When to Use Shielding

[`asyncio.shield()`][asyncio-shield] is appropriate when **all** of the
following are true:

1. **The work is short.** A database commit, a single network frame, or
   a file buffer flush -- seconds at most, not minutes.
2. **Interrupting it would leave things in a worse state.** A
   half-finished commit, a transaction that must finish rolling back, or
   a flush that must complete to avoid data loss.
3. **A plain `#!py try`/`#!py finally` is not enough.** You have a real
   must-finish step that requires `#!py await`, and a second
   cancellation could interrupt it.
4. **You have an explicit owner.** A longer-lived
   [`TaskGroup`][taskgroup] or equivalent scope will observe the task's
   result or exception.

If the work is long-running, or you find yourself shielding an entire
writer task, that is a design smell. Keep the critical step small and
let the rest cooperate with cancellation normally.

Sometimes that critical step is not a single `#!py await`, but a short
final phase with two or three awaited steps -- for example, flushing a
file, moving it into place, and syncing the directory. The same rule
applies: keep that phase small, give it an owner, and shield only when
interrupting it would leave things in a worse state.

### Timeout or Shield?

When cleanup or finalisation itself needs to `#!py await`,
[`asyncio.shield()`][asyncio-shield] is still not the default. Start by
asking whether the work is best-effort or must-finish.

For best-effort cleanup, prefer a small
[`asyncio.timeout()`][asyncio-timeout] around the awaited step. This
keeps shutdown bounded and preserves structured control flow.

For must-finish cleanup, either move the work into a longer-lived owner
such as a [`TaskGroup`][taskgroup], or use
[`asyncio.shield()`][asyncio-shield] around only the smallest critical
step after you have created and stored the inner task.

Timeout-bounded cleanup trades completeness for bounded latency.
Shielded cleanup trades bounded latency for a better chance of
completion. Pick the failure mode that is safer for your program.

Shielding is not an exception to the "never swallow cancellation" rule
from [Cancellation and
Timeouts](../the-basics/cancellation-and-timeouts.md). The outer task is
still cancelled. What makes shielding special is that one small inner
operation is allowed to finish under separate ownership. If you cannot
name that owner, you do not need [`asyncio.shield()`][asyncio-shield] --
you need a redesign.

!!! Warning

    Before you call [`asyncio.shield()`][asyncio-shield], answer three
    questions:

    1. Who stores the task?
    2. Who awaits it later?
    3. Who handles its exception?

    If you cannot answer all three, do not use
    [`asyncio.shield()`][asyncio-shield].

[asyncio-shield]: https://docs.python.org/3/library/asyncio-task.html#asyncio.shield
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[exceptiongroup]: https://docs.python.org/3/library/exceptions.html#ExceptionGroup
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[trio-docs]: https://trio.readthedocs.io/en/stable/
[trio-cancel-scopes]: https://trio.readthedocs.io/en/stable/reference-core.html#cancellation-and-timeouts
