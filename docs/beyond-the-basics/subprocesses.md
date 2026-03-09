---
title: Subprocesses
description: >-
  Run external commands asynchronously with asyncio.create_subprocess_exec()
  and asyncio.create_subprocess_shell(). Stream stdin, stdout, and stderr
  without blocking the event loop.
---

# Subprocesses

Running external commands is a common need in async programs. You might be
shelling out to `ffmpeg` to transcode a video, running `git` to inspect a
repository, or piping data through a command-line tool. The standard library's
`subprocess` module works fine for synchronous code, but calling it from an
async context blocks the event loop -- the same problem you saw in
[Blocking Code](blocking-code.md). Asyncio provides its own subprocess APIs
that let you launch processes, stream their output, and wait for them to
finish, all without blocking.

## `create_subprocess_exec()`

[`asyncio.create_subprocess_exec()`][asyncio-create-subprocess-exec]
is the primary way to run an external command. You pass the program and its
arguments as separate strings -- just like `subprocess.Popen` with a list --
and get back a
[`Process`][process]
object:

```python title="subprocess_exec.py"
import asyncio
from asyncio.subprocess import Process

async def main() -> None:
    proc: Process = await asyncio.create_subprocess_exec(
        "echo", "hello", "from", "subprocess",
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    print(f"Output: {stdout.decode().strip()}")
    print(f"Return code: {proc.returncode}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python subprocess_exec.py"
Output: hello from subprocess
Return code: 0
```

A few things to note:

- **`stdout=asyncio.subprocess.PIPE`** tells asyncio to capture the process's
  standard output. Without it, stdout goes directly to the terminal and you
  cannot read it from Python.
- **`asyncio.subprocess.DEVNULL`** discards output entirely -- useful when you
  only care about the exit code.
- **`communicate()`** waits for the process to finish and returns `(stdout,
  stderr)` as bytes. More on this below.

!!! note

    `asyncio.subprocess.PIPE` and `asyncio.subprocess.DEVNULL` are the same
    constants as `subprocess.PIPE` and `subprocess.DEVNULL`. You can use
    either import. This guide uses `asyncio.subprocess.*` for clarity.

To capture stderr, add `stderr=asyncio.subprocess.PIPE`. The `communicate()`
call returns both streams as `(stdout_bytes, stderr_bytes)`.

## `create_subprocess_shell()`

[`asyncio.create_subprocess_shell()`][asyncio-create-subprocess-shell]
runs a command through the system shell (`/bin/sh` on Unix, `cmd.exe` on
Windows). You pass the entire command as a single string:

```python title="subprocess_shell.py"
import asyncio
from asyncio.subprocess import Process

async def main() -> None:
    proc: Process = await asyncio.create_subprocess_shell(
        "echo hello && echo world",
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    print(stdout.decode().strip())

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python subprocess_shell.py"
hello
world
```

The shell gives you access to features like `&&` chaining, pipes (`|`), glob
expansion, and environment variable substitution. That convenience comes at a
cost:

!!! danger

    **Never pass untrusted input to `create_subprocess_shell()`.** Shell
    injection is a serious security vulnerability -- an attacker-controlled
    string can execute arbitrary commands. If the command or any of its
    arguments come from user input, use `create_subprocess_exec()` instead.
    It passes arguments directly to the process without shell
    interpretation.

Prefer `create_subprocess_exec()` as your default. Reach for
`create_subprocess_shell()` only when you genuinely need shell features like
pipelines or glob expansion, and only with command strings you fully control.

## [`Process.communicate()`][process-communicate]

[`Process.communicate()`][process-communicate]
is the workhorse method for subprocess interaction. It sends data to stdin (if
provided), closes stdin so the child knows input is complete, reads all of
stdout and stderr into memory, and waits for the process to exit. It returns
a `(stdout_bytes, stderr_bytes)` tuple:

```python title="subprocess_communicate.py"
import asyncio
from asyncio.subprocess import Process

async def main() -> None:
    # Feed input to a process via stdin
    proc: Process = await asyncio.create_subprocess_exec(
        "python", "-c",
        "import sys; data = sys.stdin.read(); print(f'Got {len(data)} bytes')",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    input_data: bytes = b"hello world\n" * 100
    stdout, _ = await proc.communicate(input=input_data)
    print(stdout.decode().strip())
    print(f"Return code: {proc.returncode}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python subprocess_communicate.py"
Got 1200 bytes
Return code: 0
```

`communicate()` handles stdin, stdout, and stderr concurrently -- it will not
deadlock even if the child writes enough output to fill the OS pipe buffer
while you are still sending input. This is the same reason
`subprocess.Popen.communicate()` exists in the synchronous world: manual reads
and writes can deadlock, `communicate()` cannot.

!!! tip

    If you opened a pipe for stdout or stderr but used `wait()` instead of
    `communicate()`, you risk a deadlock. The child blocks writing to a full
    pipe buffer, and your code blocks waiting for the child to exit. Always
    use `communicate()` when you need to collect output, or read streams
    manually as shown in the next section.

## Streaming Output

Sometimes the child process runs for a long time and you want to process its
output as it arrives rather than waiting for it to finish.
`Process.stdout` and `Process.stderr` are
[`StreamReader`](../the-basics/streams.md)
objects when you open them with `PIPE`, so you can read line by line:

```python title="subprocess_streaming.py"
import asyncio
from asyncio.subprocess import Process

async def main() -> None:
    proc: Process = await asyncio.create_subprocess_exec(
        "python", "-c",
        (
            "import time, sys\n"
            "for i in range(5):\n"
            "    print(f'step {i}', flush=True)\n"
            "    time.sleep(0.3)\n"
        ),
        stdout=asyncio.subprocess.PIPE,
    )

    assert proc.stdout is not None
    while True:
        line: bytes = await proc.stdout.readline()
        if not line:
            break
        print(f"[live] {line.decode().strip()}")

    await proc.wait()
    print(f"Process exited with code {proc.returncode}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python subprocess_streaming.py"
[live] step 0
[live] step 1
[live] step 2
[live] step 3
[live] step 4
Process exited with code 0
```

Each line appears as soon as the child flushes it. This pattern is useful for
tailing log files, monitoring build progress, or forwarding output in real
time. Note the `flush=True` on the child side -- without it, Python buffers
stdout when it is not connected to a terminal, and lines arrive in large
chunks instead of one at a time.

!!! warning

    When you read streams manually, you **must** still call
    `await proc.wait()` after you finish reading. This ensures the process's
    resources are cleaned up. Skipping `wait()` can leave zombie processes
    on Unix systems.

## Timeouts

Subprocesses can hang. A downstream service might stall, a command might wait
for input you never send, or a bug might cause an infinite loop. Wrap
subprocess operations in
[`asyncio.timeout()`][asyncio-timeout]
to enforce a deadline:

```python title="subprocess_timeout.py"
import asyncio
from asyncio.subprocess import Process

async def main() -> None:
    proc: Process = await asyncio.create_subprocess_exec(
        "sleep", "30",
    )
    try:
        async with asyncio.timeout(2):
            await proc.wait()
            print("Process finished in time")
    except TimeoutError:
        print(f"Timed out — killing process (pid {proc.pid})")
        proc.kill()
        await proc.wait()  # Always wait after kill
        print(f"Process killed, return code: {proc.returncode}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python subprocess_timeout.py"
Timed out — killing process (pid 12345)
Process killed, return code: -9
```

When the timeout fires, [`asyncio.timeout()`][asyncio-timeout] raises [`TimeoutError`][timeouterror]. At that
point the child process is still running -- the timeout cancelled your *await*,
not the subprocess itself. You need to explicitly kill it with
[`proc.kill()`][proc-kill]
(sends `SIGKILL` on Unix) or
[`proc.terminate()`][proc-terminate]
(sends `SIGTERM` on Unix, giving the process a chance to clean up). After
killing, you still need `await proc.wait()` to reap the process.

!!! note

    [`proc.kill()`][proc-kill] and [`proc.terminate()`][proc-terminate] are *not* coroutines -- they send
    the signal immediately and return. The `await proc.wait()` afterward is
    what actually waits for the process to exit and collects its return
    code.

## Resource Management

The single most important rule with async subprocesses: **always wait for the
process to finish**. Every `create_subprocess_exec()` or
`create_subprocess_shell()` call should have a corresponding `await
proc.wait()` or `await proc.communicate()` somewhere. If you don't, you risk
leaving zombie processes behind, leaking file descriptors, or missing error
output.

The safest pattern is `try`/`except` with kill-and-wait on the error path:

```python title="subprocess_cleanup.py"
import asyncio
from asyncio.subprocess import Process

async def run_with_timeout(
    command: list[str],
    timeout_seconds: float,
    input_data: bytes | None = None,
) -> tuple[bytes, bytes, int]:
    """Run a command with a timeout. Returns (stdout, stderr, returncode)."""
    proc: Process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE if input_data else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(timeout_seconds):
            stdout, stderr = await proc.communicate(input=input_data)
    except (asyncio.CancelledError, TimeoutError):
        proc.kill()
        await proc.wait()
        raise
    assert proc.returncode is not None
    return stdout, stderr, proc.returncode

async def main() -> None:
    stdout, stderr, code = await run_with_timeout(
        ["python", "-c", "print('hello')"],
        timeout_seconds=5.0,
    )
    print(f"stdout: {stdout.decode().strip()}")
    print(f"code:   {code}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python subprocess_cleanup.py"
stdout: hello
code:   0
```

The pattern handles three cases:

1. **Normal completion** -- `communicate()` finishes, you inspect the return
   code.
2. **Cancellation** -- the parent task is
   [cancelled](../the-basics/cancellation-and-timeouts.md) while
   waiting. You kill the
   child process, wait for it to actually exit, and re-raise.
3. **Timeout** -- the [`asyncio.timeout()`][asyncio-timeout] fires, and [`TimeoutError`][timeouterror] follows
   the same cleanup path as cancellation.

This `run_with_timeout` helper is a solid building block. Adapt it to your
needs -- add logging, check return codes, decode output -- but keep the
`try`/`except`/`kill`/`wait` skeleton intact.

!!! warning

    Do not rely on the garbage collector to clean up processes. On CPython,
    a [`Process`][process] object going out of scope may eventually close its pipes,
    but the child process itself keeps running until explicitly waited on or
    killed. Explicit cleanup makes the behaviour deterministic.

---

[asyncio-create-subprocess-exec]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_exec
[process]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process
[asyncio-create-subprocess-shell]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.create_subprocess_shell
[process-communicate]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.communicate
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[timeouterror]: https://docs.python.org/3/library/exceptions.html#TimeoutError
[proc-kill]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.kill
[proc-terminate]: https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.subprocess.Process.terminate