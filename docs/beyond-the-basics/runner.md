---
title: Runner
description: >-
  Use asyncio.Runner to run multiple top-level coroutines on the same
  event loop. Ideal for test harnesses, REPL experimentation, and
  orchestrating setup/work/teardown steps that each need await.
---

# Runner

Every example in this guide ends the same way:
[`asyncio.run(main())`](../the-basics/getting-started.md#coroutines-and-asynciorun).
That call creates a fresh event loop, runs your coroutine to completion, and
tears the loop down. One shot, one loop. Most of the time that is exactly
what you want.

But sometimes you need to run *several* top-level coroutines on the *same*
loop -- without building them all into a single `#!py main()`. Maybe you are
driving async code from a synchronous test harness, experimenting in a REPL,
or orchestrating setup/work/teardown steps that each need [`await`][await]. For this,
Python 3.11 added
[`asyncio.Runner`][asyncio-runner].

## Using [`asyncio.Runner`][asyncio-runner]

`Runner` is a context manager that holds an event loop open for as long as you
need it. Inside the `with` block you call `#!py runner.run()` as many times as you
like -- each call executes one coroutine to completion on the same loop:

```python title="runner_basic.py"
import asyncio


async def greet(name: str) -> str:
    await asyncio.sleep(0.1)
    return f"Hello, {name}"


async def farewell(name: str) -> str:
    await asyncio.sleep(0.1)
    return f"Goodbye, {name}"


if __name__ == "__main__":
    with asyncio.Runner() as runner:
        print(runner.run(greet("Alice")))
        print(runner.run(farewell("Alice")))
```

```text title="$ python runner_basic.py"
Hello, Alice
Goodbye, Alice
```

Both coroutines ran on the same event loop. Any state tied to that loop --
cached connections, background tasks, async generators -- survives between
calls.

Compare this to calling [`asyncio.run()`][asyncio-run] twice:

```python
# two_runs.py  (works, but creates two separate loops)
import asyncio

async def greet(name: str) -> str:
    await asyncio.sleep(0.1)
    return f"Hello, {name}"

async def farewell(name: str) -> str:
    await asyncio.sleep(0.1)
    return f"Goodbye, {name}"

if __name__ == "__main__":
    print(asyncio.run(greet("Alice")))
    print(asyncio.run(farewell("Alice")))
```

This creates two loops. Any loop-bound state from the first call is gone by
the second. For trivial examples that is fine, but it matters when you have
resources that live on the loop.

## When Runner Beats [`asyncio.run()`][asyncio-run]

**Shared state across coroutines.** If you initialize a connection pool in
your first coroutine, a `Runner` keeps that pool alive for subsequent calls.
With separate [`asyncio.run()`][asyncio-run] calls the pool would be created and destroyed
each time.

```python title="runner_shared_state.py"
import asyncio


class FakePool:
    """Simulates an async connection pool."""

    def __init__(self) -> None:
        self.connection_count: int = 0

    async def connect(self) -> None:
        await asyncio.sleep(0.1)
        self.connection_count += 1
        print(f"pool: connected (total: {self.connection_count})")

    async def query(self, sql: str) -> str:
        await asyncio.sleep(0.05)
        return f"result of {sql!r} (connections: {self.connection_count})"


pool = FakePool()


async def setup() -> None:
    await pool.connect()
    await pool.connect()


async def work() -> None:
    result: str = await pool.query("SELECT 1")
    print(result)


if __name__ == "__main__":
    with asyncio.Runner() as runner:
        runner.run(setup())
        runner.run(work())
```

```text title="$ python runner_shared_state.py"
pool: connected (total: 1)
pool: connected (total: 2)
result of 'SELECT 1' (connections: 2)
```

**Test suites.** When testing async code from a synchronous test runner, you
can create a `Runner` once per session (or once per test class) and reuse it.
This avoids the overhead of spinning up a new loop for every test and lets
fixtures like database connections persist across tests.

**REPL experimentation.** If you are driving async calls from a plain Python
shell, a `Runner` lets you call `#!py runner.run()` interactively without
restarting the loop each time.

## Runner in Tests

Here is a pattern for pytest where a single `Runner` backs an entire test
module. Each test calls `#!py runner.run()` to execute its async code:

```python title="test_with_runner.py"
import asyncio
from typing import Iterator

import pytest


@pytest.fixture(scope="module")
def runner() -> Iterator[asyncio.Runner]:
    with asyncio.Runner() as r:
        yield r


async def fetch_value() -> int:
    await asyncio.sleep(0.01)
    return 42


async def fetch_double(n: int) -> int:
    await asyncio.sleep(0.01)
    return n * 2


def test_fetch_value(runner: asyncio.Runner) -> None:
    result: int = runner.run(fetch_value())
    assert result == 42


def test_fetch_double(runner: asyncio.Runner) -> None:
    result: int = runner.run(fetch_double(21))
    assert result == 42
```

!!! tip

    This is useful when you need fine-grained control or cannot use
    [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio). If you
    *can* use pytest-asyncio, its `@pytest.mark.asyncio` decorator is
    usually simpler.

## `#!py Runner.close()`

When the `with` block exits, `#!py Runner.close()` is called automatically. It
does the same cleanup that [`asyncio.run()`][asyncio-run] does at the end of its single
call (see [Shutdown Sequence](../how-asyncio-works/shutdown-sequence.md)
for the full details):

1. Cancels all remaining tasks.
2. Shuts down all async generators
   ([`shutdown_asyncgens`][shutdown-asyncgens]).
3. Shuts down the default executor
   ([`shutdown_default_executor`][shutdown-default-executor]).
4. Closes the event loop.

You can also call `#!py runner.close()` manually if you are not using the context
manager form, but the `with` statement is strongly preferred -- it guarantees
cleanup even if an exception is raised.

!!! warning

    After `#!py close()`, the `Runner` is spent. Calling `#!py runner.run()` again
    will raise `RuntimeError`. If you need another loop, create a new
    `Runner`.

---

[await]: https://docs.python.org/3/reference/expressions.html#await
[asyncio-runner]: https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner
[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[shutdown-asyncgens]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.shutdown_asyncgens
[shutdown-default-executor]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.shutdown_default_executor