---
title: Runner
description: >-
  A concise guide to asyncio.Runner. Learn when it is better than
  asyncio.run(), what it buys you in tests and REPLs, and where to read the
  official reference next.
---

# Runner

Most programs should call [`asyncio.run()`][asyncio-run] once and stop thinking
about loop management.

[`asyncio.Runner`][asyncio-runner] exists for the smaller set of cases where you
need to run *multiple* top-level coroutines on the *same* event loop without
cramming them into one giant `#!py main()`.

This is a good example of a topic where the official docs are already strong.
This section stays focused on when [`asyncio.Runner`][asyncio-runner] is worth
it.

## When to Use `#!py Runner`

Reach for [`asyncio.Runner`][asyncio-runner] when all of the following are
true:

- you are still at the top level of the program
- you need more than one `#!py run(...)` call
- those calls should share one loop and one async context

Common cases:

- synchronous test harnesses
- REPL experiments
- setup/work/teardown steps driven from sync code

## The Shape of the API

```python title="runner_basic.py"
import asyncio


async def setup() -> None:
    await asyncio.sleep(0.1)
    print("setup")


async def work() -> None:
    await asyncio.sleep(0.1)
    print("work")


if __name__ == "__main__":
    with asyncio.Runner() as runner:
        runner.run(setup())
        runner.run(work())
```

Both coroutines run on the same loop. That is the whole point.

## When `#!py asyncio.run()` Is Still Better

If you only need one top-level async entry point, [`asyncio.run()`][asyncio-run] is simpler,
clearer, and more idiomatic.

If you need multiple pieces of async work but they naturally belong together,
write one `#!py main()` and keep [`asyncio.Runner`][asyncio-runner] out of it.

## Cleanup

[`asyncio.Runner`][asyncio-runner] cleans up the same broad categories of state
as [`asyncio.run()`][asyncio-run]:

- remaining tasks
- async generators
- the default executor
- the loop itself

Use `#!py with asyncio.Runner() as runner:` so cleanup still happens if one
`#!py runner.run(...)` call raises.

## What to Read Next

- Full reference and SIGINT behavior: [Runners][runners]
- Shutdown details: [Shutdown Sequence](../how-asyncio-works/shutdown-sequence.md)

[asyncio-run]: https://docs.python.org/3/library/asyncio-task.html#asyncio.run
[asyncio-runner]: https://docs.python.org/3/library/asyncio-runner.html#asyncio.Runner
[runners]: https://docs.python.org/3/library/asyncio-runner.html
