# Shielding

Previous: [Blocking Code](blocking-code.md)
Next: [Custom Context Managers](custom-context-managers.md)

Sometimes you genuinely need work to survive cancellation. A database
transaction is half-committed, a websocket client needs to send a goodbye
frame, a buffer must flush before the process exits. In these situations the
right move is not to fight the cancellation system -- it is to *shield* a
small, critical piece of work from it while letting everything else wind down
normally.

[`asyncio.shield()`](https://docs.python.org/3/library/asyncio-task.html#asyncio.shield)
is the tool for this job. It is a sharp tool -- use it deliberately.

## What `shield()` Does

`asyncio.shield()` wraps an awaitable so that cancelling the *outer* task does
not cancel the *inner* work. Under the hood it creates a new `Future` that
acts as a proxy. When the outer task is cancelled, the proxy future receives
the `CancelledError`, but the underlying task keeps running:

```python
# shield_basic.py
import asyncio


async def critical_write(data: str) -> str:
    """Simulate a write that must not be interrupted."""
    print(f"write: starting ({data!r})")
    await asyncio.sleep(1)  # Simulate I/O
    print(f"write: finished ({data!r})")
    return "ok"


async def handler() -> None:
    try:
        result: str = await asyncio.shield(critical_write("payload"))
        print(f"handler: got {result}")
    except asyncio.CancelledError:
        print("handler: cancelled, but the write continues in the background")
        raise  # Always re-raise -- Chapter 1 rule still applies


async def main() -> None:
    task: asyncio.Task[None] = asyncio.create_task(handler())
    await asyncio.sleep(0.2)       # Let handler start
    task.cancel()                   # Cancel the outer task
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(1.5)       # Give the shielded work time to finish
    print("main: done")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python shield_basic.py
write: starting ('payload')
handler: cancelled, but the write continues in the background
write: finished ('payload')
main: done
```

The handler was cancelled after 0.2 seconds, but `critical_write` ran to
completion. That is the whole point of `shield()`.

> [!NOTE]
> Notice that the `except CancelledError` block still re-raises. Shielding
> protects the *inner* awaitable -- it does not change the fact that the
> *outer* task has been cancelled. You are not swallowing cancellation here;
> you are splitting one piece of work off so it can finish independently.

## When to Use It

`shield()` is appropriate when all of the following are true:

1. **The work is short.** A database commit, a single network frame, a buffer
   flush -- seconds at most, not minutes.
2. **Interrupting it would leave things in a bad state.** A half-committed
   transaction, a protocol that requires a closing handshake, an incomplete
   file write.
3. **You have thought about ownership.** You know who will observe the
   shielded task's result or exception, and how long it is allowed to run.

Common legitimate uses:

- **Database commit/rollback** -- the transaction must complete once started.
- **Sending a goodbye message** -- a websocket or protocol peer expects a
  close frame.
- **Flushing a write buffer** -- partial writes corrupt data.
- **Logging or metrics flush** -- telemetry that would be lost if abandoned.
- **Graceful-shutdown cleanup** -- releasing external leases or locks.

If the work is long-running, or you find yourself shielding an entire request
handler, that is a design smell. Restructure so that the critical part is
small and the rest cooperates with cancellation normally.

## The Sharp Edge

Here is the uncomfortable truth: `shield()` creates *unstructured* work. The
shielded coroutine keeps running with no parent, no `TaskGroup`, no scope. If
it raises an exception, nobody is listening. If it runs forever, nobody will
cancel it. You have punched a hole in structured concurrency.

Let's make this concrete. The example below shields a slow write inside a
timeout. The timeout fires, the handler exits -- but the write is still
running in the background with no owner:

```python
# shield_orphan.py
import asyncio


async def slow_write(data: str) -> None:
    print(f"write: starting ({data!r})")
    await asyncio.sleep(5)
    print(f"write: finished ({data!r})")


async def handler(data: str) -> None:
    try:
        async with asyncio.timeout(0.5):
            await asyncio.shield(slow_write(data))
    except TimeoutError:
        print("handler: timed out")
    print("handler: returning")


async def main() -> None:
    await handler("important")
    print("main: handler returned, but is the write still running?")
    await asyncio.sleep(6)  # Wait and see


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python shield_orphan.py
write: starting ('important')
handler: timed out
handler: returning
main: handler returned, but is the write still running?
write: finished ('important')
```

The write finished five seconds after the handler returned. During those five
seconds it was a ghost -- no `TaskGroup` watching it, no caller awaiting its
result, no way to cancel it if the program needed to shut down. If
`slow_write` had raised an exception, you would get a "Task exception was
never retrieved" warning and nothing else.

> [!WARNING]
> Every call to `shield()` is a promise: "I know this work will outlive its
> caller, and I have arranged for someone else to own it." If you cannot point
> to that owner, do not use `shield()`.

## Safe Patterns

The fix is always the same: give the shielded work an *explicit owner*. Here
are two patterns that work well in practice.

### Pattern 1: Store a Reference and Await It

Keep a reference to the inner task and make sure something awaits it before
the program exits. This is the simplest approach when you have a clear
shutdown path:

```python
# shield_safe_reference.py
import asyncio


async def flush_buffer(data: str) -> None:
    print(f"flush: writing {data!r}")
    await asyncio.sleep(1)
    print(f"flush: done")


async def handler(
    data: str,
    pending: list[asyncio.Task[None]],
) -> None:
    task: asyncio.Task[None] = asyncio.create_task(flush_buffer(data))
    pending.append(task)  # Register ownership
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        print("handler: cancelled, flush continues")
        raise


async def main() -> None:
    pending: list[asyncio.Task[None]] = []
    task: asyncio.Task[None] = asyncio.create_task(handler("batch-1", pending))
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Await all shielded work before exiting
    if pending:
        print(f"main: waiting for {len(pending)} pending flush(es)")
        for t in pending:
            await t
    print("main: all flushed, exiting cleanly")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python shield_safe_reference.py
flush: writing 'batch-1'
handler: cancelled, flush continues
main: waiting for 1 pending flush(es)
flush: done
main: all flushed, exiting cleanly
```

The key difference from the orphan example: `main()` holds a reference to the
flush task and awaits it before exiting. The shielded work has an owner.

> [!TIP]
> Notice you pass the *task* to `shield()`, not the coroutine directly. When
> you write `asyncio.shield(some_coroutine())`, shield creates the task for
> you internally, and you have no reference to it. By creating the task
> yourself first, you keep a handle you can store, await, or cancel later.

### Pattern 2: A Dedicated Cleanup TaskGroup

For server-style code where many requests might shield work concurrently, use
a `TaskGroup` that outlives individual request handlers. Shielded tasks get
added to this group, which is awaited during shutdown:

```python
# shield_safe_taskgroup.py
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def cleanup_scope() -> AsyncIterator[asyncio.TaskGroup]:
    """A TaskGroup that owns all shielded cleanup work."""
    async with asyncio.TaskGroup() as tg:
        yield tg
    # When this exits, all cleanup tasks have finished


async def send_goodbye(conn_id: str) -> None:
    print(f"goodbye: sending close frame to {conn_id}")
    await asyncio.sleep(0.5)
    print(f"goodbye: sent to {conn_id}")


async def handle_request(
    conn_id: str,
    cleanup: asyncio.TaskGroup,
) -> None:
    try:
        print(f"request: handling {conn_id}")
        await asyncio.sleep(10)  # Simulate work
    except asyncio.CancelledError:
        cleanup.create_task(send_goodbye(conn_id))
        raise


async def main() -> None:
    async with cleanup_scope() as cleanup:
        task: asyncio.Task[None] = asyncio.create_task(
            handle_request("conn-42", cleanup)
        )
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        print("main: request handler done, cleanup group still running")
    # cleanup_scope().__aexit__ waits for send_goodbye to finish
    print("main: all cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
```

```text
$ python shield_safe_taskgroup.py
request: handling conn-42
goodbye: sending close frame to conn-42
goodbye: sent to conn-42
main: request handler done, cleanup group still running
main: all cleanup complete
```

The `cleanup` `TaskGroup` outlives the request handler. When the program
shuts down, exiting `cleanup_scope()` waits for all goodbye messages to be
sent. Every shielded task has a parent.

## Testing Shielded Code

To verify that shielding works, cancel the outer task and then check that the
inner work completed. The pattern is straightforward:

```python
# test_shield.py
import asyncio


async def db_commit(committed: list[bool]) -> None:
    await asyncio.sleep(0.3)
    committed.append(True)


async def test_shield_protects_commit() -> None:
    committed: list[bool] = []
    task: asyncio.Task[None] = asyncio.create_task(db_commit(committed))

    async def wrapper() -> None:
        await asyncio.shield(task)

    outer: asyncio.Task[None] = asyncio.create_task(wrapper())
    await asyncio.sleep(0.1)
    outer.cancel()
    try:
        await outer
    except asyncio.CancelledError:
        pass

    # The shielded task should still complete
    await task
    assert committed == [True], "db_commit should have finished"
    print("PASSED: shielded commit completed despite outer cancellation")


if __name__ == "__main__":
    asyncio.run(test_shield_protects_commit())
```

```text
$ python test_shield.py
PASSED: shielded commit completed despite outer cancellation
```

The same approach works in pytest with
[`pytest-asyncio`](https://github.com/pytest-dev/pytest-asyncio). Cancel the
outer task, then await the inner one and assert on its side effects.

---

`shield()` is the one legitimate exception to the "never swallow
cancellation" rule from [Chapter 1](../everyday-asyncio/cancellation-and-timeouts.md).
It exists because real systems have work that must not be interrupted --
commits, close frames, flushes. But it breaks structured concurrency by
design, so treat every use as a small, deliberate exception: keep the shielded
work short, give it an explicit owner, and make sure someone awaits the result
before the program exits. If you cannot articulate who owns the shielded task,
you do not need `shield()` -- you need a redesign.

Next up: [Custom Context Managers](custom-context-managers.md), where you will
build async context managers that compose resource lifetimes cleanly.
