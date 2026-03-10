---
title: Custom Context Managers
description: >-
  Create your own async context managers with @asynccontextmanager and
  AsyncExitStack. Learn patterns for composing async resource lifetimes
  and wrapping setup/teardown logic into reusable async with blocks.
---

# Custom Context Managers

Chapter 1 covered *using* [`async with`][async-with] with context managers that asyncio
hands you --
[`Lock`][lock],
[`TaskGroup`][taskgroup],
[`timeout()`](../the-basics/cancellation-and-timeouts.md). You know
the contract: [`__aenter__`][aenter] runs on entry, [`__aexit__`][aexit] runs on exit, cleanup
is guaranteed even under
[cancellation](../the-basics/cancellation-and-timeouts.md). This
section covers the other side: *creating* your
own async context managers so you can wrap setup/teardown logic into a clean
[`async with`][async-with] block that callers can use the same way.

## [`@asynccontextmanager`][at-asynccontextmanager]

The
[`@contextlib.asynccontextmanager`][contextlib-asynccontextmanager]
decorator is the fastest way to build an async context manager. You write an
async generator function with a single `#!py yield`, and the decorator turns it
into a full async context manager. Everything before the `#!py yield` is your
setup; everything after is your teardown.

Here is a practical example -- a reusable wrapper around a database-style
connection that must be explicitly opened and closed:

```python title="managed_connection.py"
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

class DBConnection:
    """Simulates an async database connection."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.connected: bool = False

    async def connect(self) -> None:
        await asyncio.sleep(0.1)  # Simulate handshake
        self.connected = True
        print(f"[{self.dsn}] Connected")

    async def execute(self, query: str) -> str:
        assert self.connected, "Not connected"
        await asyncio.sleep(0.05)
        return f"Result of: {query}"

    async def close(self) -> None:
        await asyncio.sleep(0.05)
        self.connected = False
        print(f"[{self.dsn}] Closed")

@asynccontextmanager
async def open_connection(dsn: str) -> AsyncIterator[DBConnection]:
    conn = DBConnection(dsn)
    await conn.connect()
    try:
        yield conn
    finally:
        await conn.close()

async def main() -> None:
    async with open_connection("postgres://localhost/mydb") as conn:
        result: str = await conn.execute("SELECT 1")
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python managed_connection.py"
[postgres://localhost/mydb] Connected
Result of: SELECT 1
[postgres://localhost/mydb] Closed
```

The `#!py yield conn` line is where the body of the caller's [`async with`][async-with] block
runs. When that block exits -- whether normally, via exception, or via
cancellation -- execution resumes after the `#!py yield`, inside the `#!py finally`
block, and `#!py conn.close()` runs.

!!! note

    The return type annotation is `AsyncIterator[DBConnection]` because the
    function is technically an async generator. The decorator wraps it so
    callers see a regular async context manager, but the annotation reflects
    the function's actual signature.

## Error Handling in [`@asynccontextmanager`][at-asynccontextmanager]

The `#!py try`/`#!py finally` around the `#!py yield` is not optional decoration -- it is
*required* if you want cleanup to run when the body raises. Without it, an
exception in the caller's block kills the generator and your teardown code
never executes:

```python title="no_try_finally.py"
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

@asynccontextmanager
async def broken_manager() -> AsyncIterator[str]:
    print("Setup")
    yield "resource"
    # BUG: this only runs on normal exit
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

```text title="$ python no_try_finally.py"
Setup
Using resource
Caught the error
```

Notice that `#!py "Teardown -- this may never run!"` never printed. The exception
terminated the generator before it reached the cleanup line. Wrap the `#!py yield`
in `#!py try`/`#!py finally` and the problem disappears:

```python
@asynccontextmanager
async def fixed_manager() -> AsyncIterator[str]:
    print("Setup")
    try:
        yield "resource"
    finally:
        print("Teardown -- always runs")
```

!!! info

    **Always** wrap the `#!py yield` in `#!py try`/`#!py finally` if your context manager
    acquires a resource that needs cleanup. There are no exceptions to this
    rule. If cleanup is not needed (e.g. the context manager only sets a
    flag), you can skip it -- but when in doubt, add the `#!py try`/`#!py finally`.

## The Class-Based Protocol

Under the hood, [`async with`][async-with] calls two dunder methods:
[`__aenter__()`][aenter]
and
[`__aexit__()`][aexit].
You can implement these directly on a class when you need to carry state
between enter and exit, or when the context manager itself *is* the resource:

```python title="class_based_cm.py"
import asyncio
import time

class Timer:
    """Async context manager that measures wall-clock time of an async block."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.elapsed: float = 0.0
        self._start: float = 0.0

    async def __aenter__(self) -> "Timer":
        self._start = time.monotonic()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.elapsed = time.monotonic() - self._start
        print(f"[{self.label}] {self.elapsed:.3f}s")

async def main() -> None:
    async with Timer("sleep test") as t:
        await asyncio.sleep(0.25)
    print(f"Elapsed was {t.elapsed:.3f}s")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python class_based_cm.py"
[sleep test] 0.250s
Elapsed was 0.250s
```

The [`__aenter__`][aenter] method returns whatever the `as` target should be -- usually
`self`. The [`__aexit__`][aexit] method receives exception information (all `#!py None` for a
clean exit). If [`__aexit__`][aexit] returns `#!py True`, the exception is suppressed; if it
returns `#!py None` or `#!py False` (the default), the exception propagates.

!!! tip

    For most resource wrappers, [`@asynccontextmanager`][at-asynccontextmanager] is shorter and easier
    to read. Reach for the class-based protocol when you need the context
    manager to be a reusable object with its own methods and attributes --
    like the `Timer` above, where callers access `.elapsed` after the block.

## [`AsyncExitStack`][asyncexitstack]

Sometimes you don't know at coding time how many context managers you need.
Maybe you're opening one connection per shard, or one file per partition, and
the count is only known at runtime.
[`contextlib.AsyncExitStack`][contextlib-asyncexitstack]
manages a dynamic collection of async context managers -- entering each one and
guaranteeing they all exit in LIFO order:

```python title="exit_stack.py"
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

- **[`enter_async_context(cm)`][enter-async-context-cm]**
  -- enters `cm` and registers its [`__aexit__`][aexit] for cleanup. Returns whatever
  `#!py cm.__aenter__()` returned.
- **[`push_async_callback(callback, /, *args, **kwds)`][push-async-callback-callback-args-kwds]**
  -- registers an arbitrary async callback to run at cleanup time. Useful for
  resources that don't have a context manager interface.
- **[`aclose()`][aclose]**
  -- explicitly unwinds the stack outside of an [`async with`][async-with] block. You rarely
  need this if you're using `#!py async with AsyncExitStack()`.

The `push_async_callback` method is handy when you need to clean up something
that doesn't follow the context manager protocol:

```python
async with AsyncExitStack() as stack:
    server = await start_server(port=8080)
    stack.push_async_callback(server.shutdown)
    # server.shutdown() will be called when the block exits
```

!!! warning

    If a context manager's [`__aexit__`][aexit] raises, the [`AsyncExitStack`][asyncexitstack] still
    proceeds to close the remaining managers. Exceptions are collected and
    re-raised as part of the standard exception handling. This is the right
    behaviour -- you don't want one failed cleanup to prevent the others
    from running.

## Composing Lifetimes

A common pattern is building one context manager on top of another. The outer
manager's setup creates inner resources, and its teardown drains or closes
them. This lets you expose a single clean interface while hiding the layered
setup underneath.

Here is a "managed pool" that opens a connection pool on enter and drains
pending work before closing connections on exit:

```python title="managed_pool.py"
import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

class ConnectionPool:
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

    async def drain(self) -> None:
        while self._pending > 0:
            await asyncio.sleep(0.01)
        print("Pool drained: no pending work")

    async def close(self) -> None:
        self._connections.clear()
        print("Pool closed: all connections released")

@asynccontextmanager
async def managed_pool(dsn: str, size: int) -> AsyncIterator[ConnectionPool]:
    pool = ConnectionPool(dsn, size)
    await pool.open()
    try:
        yield pool
    finally:
        await pool.drain()
        await pool.close()

@asynccontextmanager
async def app_context() -> AsyncIterator[ConnectionPool]:
    """Higher-level context that wires up the pool with app-specific config."""
    async with managed_pool("postgres://localhost/prod", size=3) as pool:
        print("App ready")
        yield pool
        print("App shutting down")

async def main() -> None:
    async with app_context() as pool:
        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(pool.execute("SELECT 1"))
            t2 = tg.create_task(pool.execute("SELECT 2"))
        for r in (t1.result(), t2.result()):
            print(f"  {r}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python managed_pool.py"
Pool opened: 3 connections to postgres://localhost/prod
App ready
  OK: SELECT 1
  OK: SELECT 2
App shutting down
Pool drained: no pending work
Pool closed: all connections released
```

The layering is clean: `app_context` delegates resource management to
`managed_pool` via [`async with`][async-with]. The teardown sequence is natural --
`app_context`'s "App shutting down" message runs first, then `managed_pool`
drains and closes. If you later add a cache layer or a metrics reporter, you
wrap another context manager around the existing ones, and the lifetime nesting
stays correct.

This pattern composes well with [`AsyncExitStack`][asyncexitstack] too. If `app_context` needed
a variable number of pools (say, one per tenant), it could use an
[`AsyncExitStack`][asyncexitstack] internally to manage them and still expose a single
[`async with`][async-with] interface to callers.

## When to Use Each Approach

| Approach | Best for |
|---|---|
| [`@asynccontextmanager`][at-asynccontextmanager] | Most resource wrappers. Quick to write, easy to read. Use this by default. |
| Class with [`__aenter__`][aenter]/[`__aexit__`][aexit] | When the context manager is itself a stateful object with methods callers need after the block (e.g. a timer, a session tracker). |
| [`AsyncExitStack`][asyncexitstack] | Managing a dynamic number of context managers, or bridging resources that don't have a context manager interface via `push_async_callback`. |
| Composing context managers | Layering setup/teardown of multiple resources behind a single [`async with`][async-with]. Keep lifetimes nested and explicit. |

---

[async-with]: https://docs.python.org/3/reference/compound_stmts.html#async-with
[lock]: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[aenter]: https://docs.python.org/3/reference/datamodel.html#object.__aenter__
[aexit]: https://docs.python.org/3/reference/datamodel.html#object.__aexit__
[at-asynccontextmanager]: https://docs.python.org/3/library/contextlib.html#contextlib.asynccontextmanager
[contextlib-asynccontextmanager]: https://docs.python.org/3/library/contextlib.html#contextlib.asynccontextmanager
[asyncexitstack]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack
[contextlib-asyncexitstack]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack
[enter-async-context-cm]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack.enter_async_context
[push-async-callback-callback-args-kwds]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack.push_async_callback
[aclose]: https://docs.python.org/3/library/contextlib.html#contextlib.AsyncExitStack.aclose