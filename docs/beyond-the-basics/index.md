# Beyond the Basics

Previous: [Everyday Asyncio](../01-everyday-asyncio/index.md)
Next: [How Asyncio Works](../03-how-asyncio-works/index.md)

This chapter covers patterns you will reach for once you are comfortable with
the material in Chapter 1. Everything here is still application-level code --
no event loop internals, no framework plumbing. These are the recipes and
tools that fill the gap between "I can write a TaskGroup" and "I can build a
production async service."

## Sections

1. [Blocking Code](blocking-code.md) — `asyncio.to_thread()`,
   `loop.run_in_executor()` with `ProcessPoolExecutor`, and when to reach for
   each.

2. [Shielding](shielding.md) — `asyncio.shield()`, when it is actually useful,
   and how to use it without creating orphaned tasks.

3. [Custom Context Managers](custom-context-managers.md) —
   `@asynccontextmanager`, `AsyncExitStack`, and patterns for composing async
   resource lifetimes.

4. [Advanced Coordination](advanced-coordination.md) — `Condition`, `Barrier`,
   `BoundedSemaphore`, `PriorityQueue`, `LifoQueue`.

5. [Subprocesses](subprocesses.md) — `asyncio.create_subprocess_exec()`,
   `asyncio.create_subprocess_shell()`, and working with stdin/stdout/stderr.

6. [Runner](runner.md) — `asyncio.Runner` for running multiple top-level
   coroutines in sequence, testing, and REPL use.
