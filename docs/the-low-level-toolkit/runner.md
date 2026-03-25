---
title: Runner
description: >-
  A concise guide to asyncio.Runner. Learn when to use it instead of
  asyncio.run(), what shared loop and context it buys you, and why it does
  not solve nested-loop errors.
---

# Runner

Most programs should call [`asyncio.run()`][asyncio-run] once and stop
thinking about loop management.

[`asyncio.Runner`][asyncio-runner] exists for the smaller set of cases where
synchronous top-level code needs to drive more than one async phase on the
same event loop and in the same
[`contextvars.Context`][contextvars-context].

!!! Info

    This is a reference companion section. It focuses on when
    [`asyncio.Runner`][asyncio-runner] is worth it and the footguns to
    remember. Use the official [Runners][runners] page for the full API,
    `#!py loop_factory`, debug mode, and detailed `SIGINT` handling.

## When to Use `#!py Runner`

Reach for [`asyncio.Runner`][asyncio-runner] when all of the following are
true:

- you are still at the synchronous top level of the program
- you need more than one `#!py runner.run(...)` call
- those calls should share one loop and one
  [`contextvars.Context`][contextvars-context]

Common cases:

- synchronous test harnesses
- plain REPL sessions or custom console tools
- setup/work/teardown phases driven from synchronous code

If you are already inside `#!py async def`, do not reach for
[`asyncio.Runner`][asyncio-runner]. Just `#!py await` the next operation or
structure the work under one `#!py main()`.

## The Shape of the API

```python title="runner_report.py"
import asyncio
import contextvars


request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="unset",
)


class ReportWriter:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.closed: bool = True

    async def open(self) -> None:
        await asyncio.sleep(0.05)
        self.loop = asyncio.get_running_loop()
        self.closed = False
        print("writer: opened")

    async def write_line(self, line: str) -> None:
        if self.closed:
            raise RuntimeError("writer is closed")
        await asyncio.sleep(0.05)
        print(f"write: {line}")

    async def aclose(self) -> None:
        if self.closed:
            return
        await asyncio.sleep(0.05)
        self.closed = True
        print("writer: closed")


async def setup_writer() -> ReportWriter:
    request_id.set("demo-42")
    writer = ReportWriter()
    await writer.open()
    return writer


async def generate_report(writer: ReportWriter) -> None:
    same_loop: bool = asyncio.get_running_loop() is writer.loop
    await writer.write_line(f"request_id={request_id.get()}")
    print(f"request_id: {request_id.get()}")
    print(f"same loop: {same_loop}")


async def close_writer(writer: ReportWriter) -> None:
    await writer.aclose()


if __name__ == "__main__":
    with asyncio.Runner() as runner:
        writer = runner.run(setup_writer())
        try:
            print("sync code can run here too")
            runner.run(generate_report(writer))
        finally:
            runner.run(close_writer(writer))
```

```text title="$ python runner_report.py"
writer: opened
sync code can run here too
write: request_id=demo-42
request_id: demo-42
same loop: True
writer: closed
```

[`asyncio.Runner`][asyncio-runner] is a context manager. Inside the
`#!py with` block, each `#!py runner.run(...)` call executes a coroutine,
returns its result, and re-raises its exception in the calling synchronous
code. Ordinary synchronous code can run between those calls.

In Python 3.14+, [`asyncio.Runner.run()`][asyncio-runner-run] also accepts
other awaitables.

This example also shows the resource-management rule for
[`asyncio.Runner`][asyncio-runner]: if synchronous top-level code opens a
long-lived async resource in one call and closes it in another, keep the work
inside `#!py try`/`#!py finally`. That gives you the same cleanup guarantee
that `#!py async with` gives you inside async code.

`#!py setup_writer()` and `#!py generate_report()` run on the same loop, and
the `#!py request_id` context variable set during `#!py setup_writer()` is
still present during `#!py generate_report()`. The `#!py ReportWriter`
instance also stays bound to a live loop until `#!py close_writer()` runs.
That shared loop and shared default context are what
[`asyncio.Runner`][asyncio-runner] buys you.

## When `#!py asyncio.run()` Is Still Better

If you only need one top-level async entry point,
[`asyncio.run()`][asyncio-run] is simpler, clearer, and more idiomatic.

If you need multiple pieces of async work but they naturally belong together,
write one `#!py main()` and keep [`asyncio.Runner`][asyncio-runner] out of it.

[`asyncio.Runner`][asyncio-runner] is for synchronous code that genuinely
needs to cross the async boundary more than once.

## What `#!py Runner` Does Not Solve

[`asyncio.Runner`][asyncio-runner] still creates and owns its own event loop.
Like [`asyncio.run()`][asyncio-run], `#!py runner.run(...)` cannot be called
while another event loop is already running in the same thread.

That means [`asyncio.Runner`][asyncio-runner] is not a way around the
nested-loop error. In an async function, callback, or notebook cell that
already has loop integration, stay inside that existing async environment
instead of creating a new runner.

## Cleanup

[`asyncio.Runner.close()`][asyncio-runner-close] performs the same broad
shutdown as [`asyncio.run()`][asyncio-run]:

- cancel remaining tasks
- finalize async generators
- shut down the default executor
- close the loop and release the stored
  [`contextvars.Context`][contextvars-context]

Use `#!py with asyncio.Runner() as runner:` unless you have a strong reason
to call `#!py close()` manually. The context-manager form still cleans up if
one `#!py runner.run(...)` call raises.

That loop shutdown does not replace your own application cleanup. If one
`#!py runner.run(...)` call opens a stream, connection, or other resource for
later phases, close it explicitly in your own `#!py try`/`#!py finally`
before the runner exits.

## What to Read Next

- Full reference, `#!py run(..., context=...)`, and `SIGINT` behavior:
  [Runners][runners]
- `#!py asyncio.run()` teardown details:
  [Shutdown Sequence](../how-asyncio-works/shutdown-sequence.md)

[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[asyncio-runner]: https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner
[asyncio-runner-close]: https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner.close
[asyncio-runner-run]: https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner.run
[contextvars-context]: https://docs.python.org/3/library/contextvars.html#contextvars.Context
[runners]: https://docs.python.org/3/library/asyncio-runner.html
