---
title: Context Managers and Lifetimes
description: >-
  Design async lifetimes with class-based context managers,
  @asynccontextmanager helpers, AsyncExitStack, and patterns for composing
  setup and teardown into reusable async with blocks.
---

# Context Managers and Lifetimes

The [Resource Management](../the-basics/resource-management.md) section covered
*using* [`async with`][async-with] with context managers that asyncio hands you
-- [`Lock`][lock], [`TaskGroup`][taskgroup], and the timeout scopes from
[Cancellation and Timeouts](../the-basics/cancellation-and-timeouts.md). This
section covers the other side: designing your own async lifetimes.

When a class owns the resource, make the class itself a context manager. That
makes the managed path the default instead of a helper that callers must
remember to use. When you just need a small helper scope or a composition
layer, [`@asynccontextmanager`][at-asynccontextmanager] is often the clearest
tool. And when the number of resources is only known at runtime,
[`AsyncExitStack`][asyncexitstack] keeps the teardown structured.

## The Class-Based Protocol

Under the hood, [`async with`][async-with] calls two dunder methods:
[`__aenter__()`][aenter] and [`__aexit__()`][aexit]. When a class already has a
real lifecycle -- open/close, begin/commit-or-rollback, acquire/release -- put
that protocol on the class itself.

The protocol is also packaged as
[`AbstractAsyncContextManager`][abstractasynccontextmanager]. Inheriting from
it is optional, but it makes the intent explicit and gives type checkers a
clear async context manager shape to target. The example below uses it
directly.

Here is a database transaction that makes the managed path the ordinary path:

```python title="db_transaction.py" hl_lines="7 36-38 41-50"
import asyncio
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import override # (1)!


class DBTransaction(AbstractAsyncContextManager["DBTransaction"]): # (2)!
    """Simulates an async transaction scope."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.active: bool = False

    async def begin(self) -> None:
        await asyncio.sleep(0.05)
        self.active = True
        print(f"[{self.name}] BEGIN")

    async def execute(self, query: str) -> str:
        assert self.active, "Transaction is not active"
        await asyncio.sleep(0.05)
        print(f"[{self.name}] {query}")
        return "ok"

    async def commit(self) -> None:
        await asyncio.sleep(0.05)
        self.active = False
        print(f"[{self.name}] COMMIT")

    async def rollback(self) -> None:
        await asyncio.sleep(0.05)
        self.active = False
        print(f"[{self.name}] ROLLBACK")

    @override
    async def __aenter__(self) -> "DBTransaction":
        await self.begin()
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None: # (3)!
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()

async def main() -> None:
    async with DBTransaction("order-42") as txn:
        result: str = await txn.execute("UPDATE inventory SET reserved = 1")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

1. [`@override`][override] is only available since Python 3.12 and optional.
   You can remove it if you are using an older Python version. It only helps
   catch mistakes.
2. Inheriting from
   [`AbstractAsyncContextManager`][abstractasynccontextmanager] is optional,
   but it makes the intent explicit and gives type checkers a clear protocol to
   target.
3. The return type annotation is `#!py bool | None` because
   [`__aexit__()`][aexit] can return `#!py True` to suppress exceptions, but it
   can also return `#!py None` or `#!py False` to let them propagate. In most
   cases you want propagation, so `#!py None` is a common runtime result.

```text title="$ python db_transaction.py"
[order-42] BEGIN
[order-42] UPDATE inventory SET reserved = 1
[order-42] COMMIT
ok
```

`#!py async with DBTransaction("order-42")` is now the obvious path. The class
still exposes `#!py begin()`, `#!py commit()`, and `#!py rollback()` for manual
flows when you really need them, but the ordinary API keeps the lifetime tied
to the type itself.

The [`__aenter__()`][aenter] method returns whatever the `#!py as` target
should receive -- usually `#!py self`.

The [`__aexit__()`][aexit] method receives exception information (all `#!py
None` for a clean exit). You might notice the slightly odd return type:
`#!py bool | None`. That is because [`__aexit__()`][aexit] can control whether
exceptions propagate or not. If it returns `#!py True`, the exception is
suppressed; if it returns `#!py False` or `#!py None` (the default if the
`#!py return` is omitted), the exception propagates. If you never return
`#!py True`, you can just use `#!py None` as the return type annotation. Here
the full signature is shown so the protocol is visible in one place.

### `#!py __aexit__` and Cancellation

The *"return `#!py True` to suppress the exception"* rule includes
[`CancelledError`][cancellederror]. If the body of the `#!py async with` block
is being cancelled by a timeout, a [`TaskGroup`][taskgroup], or shutdown logic,
and your [`__aexit__()`][aexit] returns `#!py True`, the caller sees a normal
exit instead of the cancellation it requested.

The same pitfall exists if [`__aexit__()`][aexit] catches
[`CancelledError`][cancellederror] internally and does not re-raise it.
Likewise, if [`__aexit__()`][aexit] raises a new exception while cancellation
is already unwinding the block, the new exception replaces the original
cancellation.

In most async context managers, [`__aexit__()`][aexit] should do its cleanup
and return `#!py None` or `#!py False`. If that cleanup itself `#!py await`s,
keep in mind that a later cancellation can still interrupt it. For more on
those trade-offs, see [Cancellation and
Timeouts](../the-basics/cancellation-and-timeouts.md) and
[Shielding](shielding.md).

## `#!py @asynccontextmanager`

The [`@contextlib.asynccontextmanager`][at-asynccontextmanager] decorator
shines when you want a small helper scope around an operation, or when you want
to compose existing context managers without inventing a new resource-owning
class.

You write an async generator with a single `#!py yield`, and the decorator
turns it into an async context manager. Everything before the `#!py yield` runs
on entry. Everything after it runs on exit.

Here is a small helper that reports how long an operation took, including
whether it succeeded or failed:

```python title="reporting_time.py" hl_lines="13-24"
import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


async def send_report(name: str, elapsed: float, *, failed: bool = False) -> None:
    await asyncio.sleep(0.1)
    result = "failed" if failed else "succeeded"
    print(f"Sent report: {name!r} {result} in {elapsed:.2f} seconds")


@asynccontextmanager
async def reporing_time(name: str) -> AsyncIterator[None]: # (1)!
    start = time.monotonic()
    try:
        yield
    except BaseException:
        elapsed = time.monotonic() - start
        await send_report(name, elapsed, failed=True)
        raise
    else:
        elapsed = time.monotonic() - start
        await send_report(name, elapsed)


async def refresh_cache() -> None:
    await asyncio.sleep(0.25)
    print("cache data is ready")


async def main() -> None:
    print("Refreshing cache 1...")
    async with reporing_time("refresh cache 1"):
        await refresh_cache()

    print("Refreshing cache 2...")
    try:
        async with asyncio.timeout(0.2):
            async with reporing_time("refresh cache 2"):
                await refresh_cache()
    except asyncio.TimeoutError:
        print("refresh_cache() took too long and was cancelled")


if __name__ == "__main__":
    asyncio.run(main())
```

1. [`@asynccontextmanager`][at-asynccontextmanager] helpers are [async
   generators](../the-basics/resource-management.md#async-generators), but
   [`AsyncIterator[None]`][asynciterator] is shorter and enough in async
   context managers.

```text title="$ python reporting_time.py"
Refreshing cache 1...
cache data is ready
Sent report: 'refresh cache 1' succeeded in 0.25 seconds
Refreshing cache 2...
Sent report: 'refresh cache 2' failed in 0.20 seconds
refresh_cache() took too long and was cancelled
```

This helper does not own a resource. It just wraps a block with reusable entry
and exit logic. That is where the decorator feels natural: you are introducing
a scope, not modeling a new long-lived object.

If the block raises, control resumes after the `#!py yield`, the `#!py except`
block still sends a failure report, and the original exception keeps unwinding
because the helper re-raises it. The timeout in `#!py main()` shows the same
pattern under cancellation: `#!py reporing_time()` still runs its exit logic,
reports the failed operation, and then lets the cancellation propagate out as a
[`TimeoutError`](../the-basics/cancellation-and-timeouts.md#asyncio-timeout-and-timeouterror).

!!! Note

    The return type annotation should be [`AsyncGenerator`][asyncgenerator]
    instead, as any `#!py async` function that `#!py yield`s is technically an
    [async generator](../the-basics/resource-management.md#async-generators)
    that must be [`aclose()`][generator-aclose]d when it is done.

    However, the `#!py @asynccontextmanager` decorator calls
    [`aclose()`][generator-aclose] automatically when the block exits. Because
    of this it is common (and correct) to annotate `#!py @asynccontextmanager`
    helpers as the narrower [`AsyncIterator`][asynciterator] type for
    simplicity. Callers do not need the full generator interface.

## Error Handling in `#!py @asynccontextmanager`

The decorator has one footgun that the class-based protocol does not: code
after `#!py yield` only runs if control returns to the generator. If the
caller's block raises and you did not wrap the `#!py yield` in structured
exception handling, your cleanup never runs:

```python title="no_try_finally.py" hl_lines="9"
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def broken_manager() -> AsyncIterator[str]:
    print("Setup")
    yield "resource" # (1)!
    print("Teardown -- this may never run!")


async def main() -> None:
    try:
        async with broken_manager() as res:
            print(f"Using {res}")
            raise RuntimeError("boom")
    except RuntimeError:
        print("Caught the error")


if __name__ == "__main__":
    asyncio.run(main())
```

1. **BUG:** this only runs on normal exit.

```text title="$ python no_try_finally.py"
Setup
Using resource
Caught the error
```

Notice that `#!py "Teardown -- this may never run!"` never printed. The
exception terminated the generator before it reached the cleanup line. Wrap the
`#!py yield` in structured exception handling and the problem disappears. If
cleanup is the same on every exit path, `#!py try`/`#!py finally` is the
simplest form:

```python
@asynccontextmanager
async def fixed_manager() -> AsyncIterator[str]:
    print("Setup")
    try:
        yield "resource"
    finally:
        print("Teardown -- always runs")
```

When success and failure need different actions, use `#!py try`/`#!py except`/
`#!py else`, as `#!py reporing_time()` does above.

!!! Warning Cancellation

    As always, the [Never Swallow
    Cancellation](../the-basics/cancellation-and-timeouts.md#never-swallow-cancellation)
    rule applies when using the decorator. [`CancelledError`][cancellederror]
    must always be re-raised, and regular care should be taken when doing async
    cleanup. For more on those trade-offs, see [Cancellation and
    Timeouts](../the-basics/cancellation-and-timeouts.md) and
    [Shielding](shielding.md).

## `#!py AsyncExitStack`

Sometimes the number of lifetimes is only known at runtime. Maybe you are
opening one connection per shard, or one file per partition, and the count only
shows up after configuration is loaded.
[`contextlib.AsyncExitStack`][contextlib-asyncexitstack] belongs in the same
toolbox: it coordinates many context managers once you already have them and
guarantees they unwind in LIFO order.

```python title="exit_stack.py" hl_lines="20 23"
import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager


@asynccontextmanager
async def open_shard(shard_id: int) -> AsyncIterator[str]:
    print(f"  Shard {shard_id}: connecting")
    await asyncio.sleep(0.05)
    try:
        yield f"shard-{shard_id}"
    finally:
        print(f"  Shard {shard_id}: disconnecting")
        await asyncio.sleep(0.05)


async def main() -> None:
    shard_ids: list[int] = [1, 2, 3, 4]

    async with AsyncExitStack() as stack:
        shards: list[str] = []
        for sid in shard_ids:
            shard = await stack.enter_async_context(open_shard(sid))
            shards.append(shard)

        print(f"All shards open: {shards}")
        # Use all shards here...

    print("All shards closed")


if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python exit_stack.py"
  Shard 1: connecting
  Shard 2: connecting
  Shard 3: connecting
  Shard 4: connecting
All shards open: ['shard-1', 'shard-2', 'shard-3', 'shard-4']
  Shard 4: disconnecting
  Shard 3: disconnecting
  Shard 2: disconnecting
  Shard 1: disconnecting
All shards closed
```

The key methods on [`AsyncExitStack`][asyncexitstack]:

- **[`enter_async_context(cm)`][enter-async-context-cm]** -- enters `#!py cm`
  and registers its [`__aexit__()`][aexit] for cleanup. Returns whatever `#!py
  cm.__aenter__()` returned.
- **[`push_async_callback(callback, /, *args,
  **kwds)`][push-async-callback-callback-args-kwds]** -- registers an arbitrary
  async callback to run at cleanup time. Useful for resources that do not have
  a context manager interface.
- **[`aclose()`][stack-aclose]** -- explicitly unwinds the stack outside of a
  `#!py async with` block. You rarely need this if you are already using `#!py
  async with AsyncExitStack()`.

The `#!py push_async_callback()` method is handy when you need to clean up
something that does not follow the context manager protocol:

```python
async with AsyncExitStack() as stack:
    server = await start_server(port=8080)
    stack.push_async_callback(server.shutdown)
    # server.shutdown() will be called when the block exits
```

!!! Note

    If a context manager's [`__aexit__()`][aexit] raises, the
    [`AsyncExitStack`][asyncexitstack] still proceeds to close the remaining
    managers. Exceptions are collected and re-raised as part of the standard
    exception handling. That is the right behaviour: one failed cleanup should
    not prevent the others from running.

## Composing Lifetimes

A common pattern is building one context manager on top of another. The outer
manager's setup creates inner resources, and its teardown drains or releases
them. This lets you expose a single clean interface while hiding the layered
setup underneath.

Here a connection pool owns its own lifetime through the class protocol, while
`#!py app_context()` uses the decorator to add higher-level application setup
and teardown:

```python title="app_context.py" hl_lines="7 35-47 49-57 60-65"
import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from types import TracebackType
from typing import override

class ConnectionPool(AbstractAsyncContextManager["ConnectionPool"]):
    """Simulates a pool of async connections."""

    def __init__(self, dsn: str, size: int) -> None:
        self.dsn = dsn
        self.size = size
        self._connections: list[str] = []
        self._pending: int = 0

    async def open(self) -> None:
        for i in range(self.size):
            await asyncio.sleep(0.02)
            self._connections.append(f"conn-{i}")
        print(f"Pool opened: {self.size} connections to {self.dsn}")

    async def execute(self, query: str) -> str:
        self._pending += 1
        await asyncio.sleep(0.05)
        self._pending -= 1
        return f"OK: {query}"

    async def aclose(self) -> None:
        while self._pending > 0:
            await asyncio.sleep(0.01)
            self._pending -= 1
        self._connections.clear()
        print("Pool released: all connections returned")

    @override
    async def __aenter__(self) -> "ConnectionPool":
        await self.open()
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

@asynccontextmanager
async def app_context() -> AsyncIterator[ConnectionPool]:
    """Higher-level context that wires up the pool with app-specific config."""
    async with ConnectionPool("postgres://localhost/prod", size=3) as pool:
        print("App ready")
        try:
            yield pool
        finally:
            print("App shutting down")

async def main() -> None:
    async with app_context() as pool:
        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(pool.execute("SELECT 1"), name="select-1")
            t2 = tg.create_task(pool.execute("SELECT 2"), name="select-2")
        for result in (t1.result(), t2.result()):
            print(f"  {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python app_context.py"
Pool opened: 3 connections to postgres://localhost/prod
App ready
  OK: SELECT 1
  OK: SELECT 2
App shutting down
Pool released: all connections returned
```

The split here is deliberate:

- `#!py ConnectionPool` owns connections and pending work, so it implements the
  class protocol itself.
- `#!py app_context()` does not model a new resource type. It composes an
  existing context manager with application-specific setup and teardown, so the
  decorator stays lightweight and readable.

This pattern composes well with [`AsyncExitStack`][asyncexitstack] too. If
`#!py app_context()` later needed one pool per tenant, it could build those
pools with an [`AsyncExitStack`][asyncexitstack] internally and still expose
one clean `#!py async with` interface to callers.

## When to Use Each Approach

| Approach | Best for |
|---|---|
| Class protocol | Resource-owning classes, or classes that already have a real setup/teardown lifecycle. Make the managed path the default. |
| [`@asynccontextmanager`][at-asynccontextmanager] | Small helper scopes and composition layers. Use it when you want to wrap a block, not model a new resource-owning type. |
| [`AsyncExitStack`][asyncexitstack] | Managing a dynamic number of context managers, or bridging resources that only expose cleanup callbacks via `#!py push_async_callback()`. |
| Composing context managers | Building one lifetime out of several smaller ones while keeping setup and teardown order explicit. |

[async-with]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[cancellederror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
[aenter]: https://docs.python.org/3/reference/datamodel.html#object.__aenter__
[aexit]: https://docs.python.org/3/reference/datamodel.html#object.__aexit__
[asynciterator]: https://docs.python.org/3/library/collections.abc.html#collections.abc.AsyncIterator
[asyncgenerator]: https://docs.python.org/3/library/collections.abc.html#collections.abc.AsyncGenerator
[generator-aclose]: https://docs.python.org/3/reference/expressions.html#agen.aclose
[at-asynccontextmanager]: https://docs.python.org/3/library/contextlib.html#contextlib.asynccontextmanager
[abstractasynccontextmanager]: https://docs.python.org/3.11/library/contextlib.html#contextlib.AbstractAsyncContextManager
[override]: https://docs.python.org/3/library/typing.html#typing.override
[asyncexitstack]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack
[contextlib-asyncexitstack]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack
[enter-async-context-cm]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack.enter_async_context
[push-async-callback-callback-args-kwds]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack.push_async_callback
[stack-aclose]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack.aclose
