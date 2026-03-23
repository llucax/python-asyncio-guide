---
title: Subprocesses
description: >-
  A concise guide to asyncio subprocesses. Learn when to use
  create_subprocess_exec() or create_subprocess_shell(), how to avoid pipe
  deadlocks, how to stream output safely, and how to clean up timed-out
  children.
---

# Subprocesses

Running external commands is common in async programs. You might call `git`,
`ffmpeg`, or another CLI tool as one step in a larger workflow.

This is a good place to lean on the [official docs][subprocesses]. Python's
subprocess coverage is already solid, so this section stays focused on the
choices and pitfalls that matter most when you are learning asyncio.

!!! Info

    Use this section for the high-level rules: when to use exec vs shell, when
    `communicate()` is the right default, and where pipe deadlocks come from.
    Use the official docs for the full `Process` API, low-level transport
    details, and platform-specific caveats.

## Exec vs Shell

Default to [`asyncio.create_subprocess_exec()`][create-subprocess-exec]. Pass
the program and its arguments separately:

```python
proc = await asyncio.create_subprocess_exec(
    "git",
    "status",
    "--short",
    stdout=asyncio.subprocess.PIPE,
)
```

This avoids shell parsing, shell quoting rules, and most command-injection
mistakes.

Use [`asyncio.create_subprocess_shell()`][create-subprocess-shell] only when the
shell syntax is the point: pipelines, redirection, glob expansion, or `&&`
chaining.

```python
proc = await asyncio.create_subprocess_shell(
    "printf 'a\n' | wc -l",
    stdout=asyncio.subprocess.PIPE,
)
```

!!! Danger

    Never pass untrusted input to
    [`asyncio.create_subprocess_shell()`][create-subprocess-shell]. If
    attacker-controlled text reaches the command string, you have a
    shell-injection bug.

!!! Note

    Shell syntax is platform-dependent. A command string that works in `sh` on
    POSIX may not work in `cmd.exe` on Windows.
    [`create_subprocess_exec()`][create-subprocess-exec] is usually the more
    portable choice.

## The Returned `#!py Process`

Both creation functions return an [`asyncio.subprocess.Process`][process]. You
do not need the full API on day one. The pieces that matter most here are:

- [`proc.returncode`][process-returncode] is `#!py None` until the child exits.
  After that, it holds the numeric exit status.
- [`await proc.wait()`][await-proc-wait] waits only for the child to terminate
  and returns that exit status. It does not read stdout or stderr, and it does
  not close stdin for you.
- [`await proc.communicate(input=None)`][communicate] is the "handle the whole
  interaction" helper. A good mental model is: optionally send bytes to stdin,
  then read piped stdout and stderr to EOF, then do the equivalent of a final
  [`wait()`][wait]. It returns `#!py (stdout_data, stderr_data)`.

If you pass `stdin=PIPE`, [`proc.stdin`][process-stdin] is a
[`StreamWriter`][streamwriter]. If you pass `stdout=PIPE` or `stderr=PIPE`,
[`proc.stdout`][process-stdout] and [`proc.stderr`][process-stderr] are
[`StreamReader`][streamreader] instances. Those streams carry `bytes`, not
text, so decode explicitly.

## The Default Pattern: `#!py communicate()`

If you want to send optional stdin, collect stdout and stderr, and wait for the
child to finish, use [`Process.communicate()`][process-communicate].

```python title="subprocess_exec.py" hl_lines="13"
import asyncio
import sys

async def main() -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "print('hello from child')",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()
    print(stdout.decode().strip())
    print(f"return code: {proc.returncode}")
    if stderr:
        print(stderr.decode().strip())

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python subprocess_exec.py"
hello from child
return code: 0
```

This is the safest default because [`communicate()`][communicate] handles stdin
input if you provide it, drains both output pipes to EOF, and waits for the
child to exit. That already includes the completion wait, so you do not add a
second [`wait()`][wait] afterward just to be safe.

When you choose [`communicate()`][communicate], let it own the subprocess
pipes. Do not read from [`proc.stdout`][process-stdout] or
[`proc.stderr`][process-stderr] at the same time, and you do not need extra
cleanup for those read sides.

!!! Note

    On Python 3.11, [`communicate()`][communicate] closes stdin only when you
    pass `input=...`. If you open `stdin=PIPE` and the child needs EOF before
    it can finish, close [`proc.stdin`][process-stdin] yourself first. Python
    3.12+ closes stdin even when `input=None`.

!!! Warning

    [`communicate()`][communicate] buffers the captured output in memory. Use it
    when the output is reasonably small and bounded. For large or unbounded
    output, stream manually instead.

## Cleanup and Finalization

A subprocess is an owned resource even though [`Process`][process] is not an
async context manager. Once you start a child, make sure one code path always
waits for it to finish:

- [`communicate()`][communicate] if it owns the pipes
- manual stream reading plus [`wait()`][wait]
- [`terminate()`][terminate] or [`kill()`][kill] plus a final
  [`wait()`][wait] or [`communicate()`][communicate] on the cleanup path

The rule is not "always call `#!py wait()` no matter what." The rule is "every
started child needs one clear completion path." [`communicate()`][communicate]
already includes the wait.

The interrupted path is where the API gets noisy. If your coroutine owns the
child across several awaits, the shutdown path belongs in `#!py try`/`#!py
finally`, but a small helper keeps the repeated steps in one place. If you want
the managed path to become the ordinary path, wrap creation in
[`@asynccontextmanager`][at-asynccontextmanager]. This follows the same pattern
as [Context Managers and
Lifetimes](context-managers-and-lifetimes.md#asynccontextmanager): setup before
`#!py yield`, cleanup in a `#!py finally` after it.

```python title="managed_subprocess.py"
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

async def terminate_subprocess(
    proc: asyncio.subprocess.Process,
    *,
    kill_after: float = 1.0,
) -> None:
    if proc.returncode is not None:
        return

    try:
        proc.terminate()
    except ProcessLookupError:
        await proc.wait()
        return

    try:
        async with asyncio.timeout(kill_after):
            await proc.wait()
    except TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            await proc.wait()
            return
        await proc.wait()

@asynccontextmanager
async def managed_subprocess(
    program: str,
    *args: str,
    **kwargs: Any,
) -> AsyncIterator[asyncio.subprocess.Process]:
    proc = await asyncio.create_subprocess_exec(program, *args, **kwargs)
    try:
        yield proc
    finally:
        await terminate_subprocess(proc)
```

This wrapper is for ownership and forced cleanup. It makes sure the child does
not outlive its owner, but it does not preserve unread output. On the normal
success path, you still use [`communicate()`][communicate] or manual draining
plus [`wait()`][wait].

## The Main Pitfall: Pipe Deadlocks

If you open `#!py stdout=PIPE` or `#!py stderr=PIPE`, do not just call
[`await proc.wait()`][await-proc-wait] -- which waits only for termination --
and ignore the pipes. A child can block trying to write into a full OS pipe
buffer while you block waiting for it to exit.

That is why the safe default is:

- [`communicate()`][communicate] when you want all output at the end
- manual stream reading when you want output incrementally

If you read manually, you must drain every pipe you opened. If both stdout and
stderr are pipes, consume them concurrently or redirect stderr into stdout with
[`asyncio.subprocess.STDOUT`][stdout-constant].

If you did not open any pipes, [`wait()`][wait] is fine.

## Streaming Output

For long-running processes, treat [`proc.stdout`][process-stdout] and
[`proc.stderr`][process-stderr] as [`StreamReader`][streamreader] objects and
consume data as it arrives.

```python title="stream_subprocess.py" hl_lines="18-19 21"
import asyncio
import sys
from managed_subprocess import managed_subprocess # (1)!

async def main() -> None:
    async with managed_subprocess(
        sys.executable,
        "-c",
        (
            "import time\n"
            "for i in range(3):\n"
            "    print(i, flush=True)\n"
            "    time.sleep(0.2)\n"
        ),
        stdout=asyncio.subprocess.PIPE,
    ) as proc:
        assert proc.stdout is not None
        while line := await proc.stdout.readline():
            print(f"child: {line.decode().strip()}")

        await proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
```

1. To keep the noise level down, we reused the `managed_subprocess()` helper
   from the previous section.

```text title="$ python stream_subprocess.py"
child: 0
child: 1
child: 2
```

That final [`await proc.wait()`][await-proc-wait] still matters. Reading a pipe
to EOF does not by itself tell you the child has exited.

The `#!py async with managed_subprocess(...)` boundary makes ownership explicit.
If cancellation or another exception interrupts the read loop,
`#!py managed_subprocess()` still terminates the unfinished child and waits for
it before returning.

If you also opened `stderr=PIPE`, read it in parallel with stdout. If you only
care about one combined stream, set
[`stderr=asyncio.subprocess.STDOUT`][stdout-constant] and read from stdout
alone.

## Timeouts and Cleanup

[`Process.wait()`][wait] and [`Process.communicate()`][communicate] do not take
a timeout argument. Wrap them in [`asyncio.timeout()`][asyncio-timeout] when
you need a deadline.

If that timeout fires, your task stops waiting, but the subprocess keeps
running. If you own the child, terminate or kill it explicitly, then do one
final awaited cleanup step.

```python title="subprocess_timeout.py"
import asyncio
import sys
from managed_subprocess import managed_subprocess # (1)!

async def main() -> None:
    try:
        async with managed_subprocess(
            sys.executable,
            "-c",
            "import time; time.sleep(10)",
        ) as proc:
            async with asyncio.timeout(0.5):
                await proc.wait()
    except TimeoutError:
        print("deadline expired; terminating child")

    print(f"child finished with return code: {proc.returncode}")

if __name__ == "__main__":
    asyncio.run(main())
```

1. To keep the noise level down, we reused the `managed_subprocess()` helper
   from the previous section.

```text title="$ python subprocess_timeout.py"
deadline expired; terminating child
child finished with return code: -15
```

The context manager keeps the timeout example focused on the deadline logic.
When the timeout aborts the wait, `#!py managed_subprocess()` still runs its
cleanup on the way out.

This wrapper uses [`wait()`][wait] in its forced-cleanup path because this
example did not open any pipes. If you opened `#!py stdout=PIPE` or
`#!py stderr=PIPE` and you still need the remaining output, the normal success
path is [`communicate()`][communicate] or manual draining plus [`wait()`][wait].
A forced-cleanup helper like this is for the abnormal path where making sure
the child stops matters more than preserving unread output.

After the final [`wait()`][wait], [`proc.returncode`][process-returncode] is set
and the child is fully finished.

[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[asynciterator]: https://docs.python.org/3/library/collections.abc.html#collections.abc.AsyncIterator
[at-asynccontextmanager]: https://docs.python.org/3/library/contextlib.html#contextlib.asynccontextmanager
[create-subprocess-exec]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_exec
[create-subprocess-shell]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_shell
[process]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process
[process-communicate]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.communicate
[process-returncode]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.returncode
[process-stderr]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stderr
[process-stdin]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stdin
[process-stdout]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.stdout
[streamreader]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader
[streamwriter]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter
[stdout-constant]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.STDOUT
[subprocesses]: https://docs.python.org/3/library/asyncio-subprocess.html
[await-proc-wait]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.wait
[communicate]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.communicate
[kill]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.kill
[terminate]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.terminate
[wait]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.wait
