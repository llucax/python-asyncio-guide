---
title: Streams
description: >-
  Build TCP clients and servers with asyncio's Streams API. Use
  asyncio.open_connection() and asyncio.start_server() with StreamReader
  and StreamWriter for clean async networking.
---

# Streams

Everything up to this point has used [`asyncio.sleep()`][asyncio-sleep] as a stand-in for real
work. Streams are where asyncio earns its keep: actual TCP networking with
clean async/await syntax. The streams API gives you a high-level interface for
reading and writing bytes over the network -- no callbacks, no protocol
classes, just a reader and a writer that you [`await`][await] like anything else.

!!! info

    This page focuses on the stream lifecycle, backpressure, and cleanup.
    Use the official [Streams][official-streams] page for the full
    `StreamReader` and `StreamWriter` method reference.

## Opening a Client Connection

[`asyncio.open_connection()`][asyncio-open-connection]
opens a TCP connection and returns a `#!py (StreamReader, StreamWriter)` tuple. The
reader is for receiving data, the writer is for sending it.

Here is a minimal client that connects to an HTTP server, sends a request, and
reads the response:

```python title="http_client.py"
import asyncio

async def main() -> None:
    reader, writer = await asyncio.open_connection("example.com", 80)

    request: bytes = b"GET / HTTP/1.0\r\nHost: example.com\r\n\r\n"
    writer.write(request)
    await writer.drain()  # (1)!

    response: bytes = await reader.read(4096)
    print(response[:200].decode())

    writer.close()
    await writer.wait_closed()  # (2)!

if __name__ == "__main__":
    asyncio.run(main())
```

1. `#!py .write()` only buffers data -- [`.drain()`][drain] is the coroutine that
   actually waits for the buffer to flush. This is where backpressure
   happens.
2. Always call both [`.close()`][close] and [`.wait_closed()`][wait-closed]. The first starts
   the shutdown, the second waits for it to complete (including TLS
   teardown and final buffer flush).

```text title="$ python http_client.py"
HTTP/1.0 200 OK
Content-Type: text/html; charset=UTF-8
...
```

A few things to notice. `#!py open_connection()` is a coroutine -- the TCP
handshake happens during the [`await`][await]. The writer's `#!py .write()` method buffers
data synchronously (no [`await`][await]), but [`.drain()`][drain] is a coroutine that waits for
the buffer to flush. And at the end, you must call both [`.close()`][close] and
[`.wait_closed()`][wait-closed] -- more on that shortly.

!!! warning

    Always close the writer when you are done. An unclosed writer leaks a socket
    and its associated file descriptor. The reader does not need to be closed
    separately -- closing the writer shuts down the underlying connection.

## `StreamReader`

[`asyncio.StreamReader`][asyncio-streamreader]
is the read side of a stream. All of its read methods are coroutines -- each
one is a *checkpoint* that may suspend while waiting for data from the network.

The main methods:

- **[`.read(n)`][read-n]**
  -- read *up to* `n` bytes. Returns fewer if fewer are available. Returns
  `#!py b""` at EOF. This is the most common read method.
- **[`.readline()`][readline]**
  -- read until `\n` (inclusive). If EOF is reached before a newline, returns
  whatever is left.
- **[`.readexactly(n)`][readexactly-n]**
  -- read exactly `n` bytes. Raises
  [`asyncio.IncompleteReadError`][asyncio-incompletereaderror]
  if EOF is reached before `n` bytes have been read. Use this when your
  protocol defines fixed-size messages.
- **[`.readuntil(separator)`][readuntil-separator]**
  -- read until `separator` is found in the stream (inclusive). Raises
  [`asyncio.IncompleteReadError`][asyncio-incompletereaderror] if EOF comes first, or
  [`asyncio.LimitOverrunError`][asyncio-limitoverrunerror] if the internal buffer limit is exceeded before
  the separator appears.
- **[`.at_eof()`][at-eof]**
  -- returns `#!py True` if the read buffer is empty *and* the connection has been
  closed by the remote end. This is not a coroutine.

The pattern for reading until the remote end disconnects:

```python
while not reader.at_eof():
    chunk: bytes = await reader.read(4096)
    if not chunk:
        break
    process(chunk)
```

!!! tip

    [`.read(n)`][read-n] returning `#!py b""` and [`.at_eof()`][at-eof] returning `#!py True` both indicate
    EOF, but they serve different purposes. Use `#!py read()` return value checks in
    loops where you are consuming data; use `#!py at_eof()` when you need a
    non-blocking check outside of a read call.

## `StreamWriter`

[`asyncio.StreamWriter`][asyncio-streamwriter]
is the write side. Writing works differently from reading: you buffer data
synchronously, then flush asynchronously.

- **[`.write(data)`][write-data]**
  -- buffer `data` (a `bytes` object) for sending. This returns `#!py None`
  immediately -- it does **not** await. The data is queued in an internal
  buffer and sent by the event loop when the socket is ready.
- **[`.writelines(data)`][writelines-data]**
  -- buffer a list of `bytes` objects. Same as calling `#!py .write()` for each
  item, but potentially more efficient. Also not a coroutine.
- **[`.drain()`][drain]**
  -- wait for the write buffer to be flushed to the OS. This **is** a
  coroutine and a checkpoint. This is where *backpressure* happens: if the
  remote end is reading slowly, the OS send buffer fills up, and [`drain()`][drain]
  will suspend your coroutine until there is room.
- **[`.close()`][close]**
  -- initiate closing the underlying connection. Not a coroutine.
- **[`.wait_closed()`][wait-closed]**
  -- wait for the connection to actually close. This is a coroutine.

The *write/drain dance* is the core pattern: call `#!py .write()` to buffer, call
`#!py await .drain()` to flush. You must call [`drain()`][drain] after writing -- otherwise
you can pile up unbounded data in the buffer without ever giving the event loop
a chance to send it (or to tell you the remote end is gone).

```python
writer.write(b"Hello, ")
writer.write(b"world!\n")
await writer.drain()  # Flush both writes to the network
```

!!! warning

    `#!py .write()` does not raise if the connection has been lost. The error only
    surfaces when you call [`drain()`][drain] (or `#!py close()`). If you forget [`drain()`][drain],
    you may silently write into a broken pipe for a long time before noticing.

## Resource Management for Streams

Always close writers. Always call [`wait_closed()`][wait-closed] after `#!py close()`. The
[`.close()`][close] method starts the shutdown process, but [`.wait_closed()`][wait-closed] is the
coroutine that waits for it to complete -- including flushing any remaining
buffered data and tearing down the TLS layer if one exists.

The standard pattern is `#!py try`/`#!py finally`:

```python
reader, writer = await asyncio.open_connection(host, port)
try:
    writer.write(b"hello\n")
    await writer.drain()
    response: bytes = await reader.readline()
finally:
    writer.close()
    await writer.wait_closed()
```

!!! danger

    `StreamWriter` is **not** an async context manager in the standard library
    (as of Python 3.13). You cannot write `#!py async with writer:`. You must call
    [`.close()`][close] and [`.wait_closed()`][wait-closed] manually in a `#!py try`/`#!py finally` block. Some
    third-party libraries add this, but the stdlib does not provide it.

If you want to keep things tidy, you can write a small helper:

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

@asynccontextmanager
async def open_stream(
    host: str, port: int
) -> AsyncIterator[tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()
```

This lets you write `#!py async with open_stream(host, port) as (reader, writer):`
and get automatic cleanup. But understand what it does under the hood -- you
will encounter plenty of code that uses the manual pattern.

## Building a TCP Server

[`asyncio.start_server()`][asyncio-start-server]
starts a TCP server. You give it a *callback* that is called with a
`#!py (StreamReader, StreamWriter)` pair for each new incoming connection. The
callback can be a coroutine function -- asyncio will schedule it as a task
automatically.

Here is a simple echo server:

```python title="echo_server.py"
import asyncio

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    addr: tuple[str, int] = writer.get_extra_info("peername")
    print(f"New connection from {addr}")

    try:
        while True:
            data: bytes = await reader.readline()
            if not data:
                break
            print(f"Received: {data.decode().strip()!r} from {addr}")
            writer.write(data)
            await writer.drain()
    finally:
        print(f"Closing connection from {addr}")
        writer.close()
        await writer.wait_closed()

async def main() -> None:
    server: asyncio.Server = await asyncio.start_server(
        handle_client, "127.0.0.1", 8888
    )
    addrs = [s.getsockname() for s in server.sockets]
    print(f"Serving on {addrs}")

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python echo_server.py"
Serving on [('127.0.0.1', 8888)]
```

A few details worth noting.
[`asyncio.Server`][asyncio-server]
is an async context manager -- `#!py async with server:` ensures the server is
closed and cleaned up when the block exits. Inside the block,
[`server.serve_forever()`][server-serve-forever]
runs until the server is stopped or cancelled.

The callback `handle_client` is responsible for its own writer cleanup. Each
connection is handled independently -- if one client disconnects, the others
keep going. The `#!py try`/`#!py finally` ensures the writer is closed even if the
client disconnects unexpectedly or the read raises an exception.

!!! note

    `#!py start_server()` spawns each callback as an independent task. This means
    errors in one connection do not propagate to the server or to other
    connections. If you want centralised error handling, catch exceptions inside
    the callback and log them.

## Complete Example: Echo Client and Server

Let's put both sides together into a single runnable program. The server echoes
lines back, and the client sends a few messages and reads the echoes. A
[`TaskGroup`][taskgroup] starts the server, runs the client, and shuts everything down
cleanly.

```python title="echo_client_server.py"
import asyncio

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    addr = writer.get_extra_info("peername")
    try:
        while True:
            data: bytes = await reader.readline()
            if not data:
                break
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()
        print(f"Server: connection from {addr} closed")

async def run_client(port: int) -> list[str]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    results: list[str] = []

    try:
        messages: list[str] = ["Hello", "asyncio", "streams"]
        for msg in messages:
            writer.write(f"{msg}\n".encode())
            await writer.drain()

            response: bytes = await reader.readline()
            decoded: str = response.decode().strip()
            print(f"Client: sent {msg!r}, got {decoded!r}")
            results.append(decoded)
    finally:
        writer.close()
        await writer.wait_closed()

    return results

async def main() -> None:
    server: asyncio.Server = await asyncio.start_server(
        handle_client, "127.0.0.1", 0  # Port 0 = pick a free port
    )

    async with server:
        port: int = server.sockets[0].getsockname()[1]
        print(f"Server: listening on port {port}")

        async with asyncio.TaskGroup() as tg:
            client_task = tg.create_task(run_client(port))

        print(f"Results: {client_task.result()}")

if __name__ == "__main__":
    asyncio.run(main())
```

```text title="$ python echo_client_server.py"
Server: listening on port 41233
Client: sent 'Hello', got 'Hello'
Client: sent 'asyncio', got 'asyncio'
Client: sent 'streams', got 'streams'
Server: connection from ('127.0.0.1', 54321) closed
Results: ['Hello', 'asyncio', 'streams']
```

A few things to note about this example. The server uses port `0`, which tells
the OS to pick an available port -- this avoids "address already in use" errors
when running examples. The [`TaskGroup`][taskgroup] runs the client task; when the client
finishes, the group exits, and the `#!py async with server:` block exits, stopping
the server cleanly. No manual cancellation needed -- structured concurrency
takes care of shutdown.

!!! tip

    Using port `0` is a good practice for tests and examples. In production you
    will bind to a specific port, but for development it avoids a whole class of
    annoying startup errors.

## Timeouts on Stream Operations

Network operations can hang indefinitely if the remote end stops responding.
Wrap stream reads and writes in
[`asyncio.timeout()`][asyncio-timeout]
to enforce deadlines:

```python title="stream_timeout.py"
import asyncio

async def cautious_read(
    reader: asyncio.StreamReader,
    timeout_seconds: float,
) -> bytes | None:
    try:
        async with asyncio.timeout(timeout_seconds):
            data: bytes = await reader.readline()
            return data if data else None
    except TimeoutError:
        print("Read timed out")
        return None

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    addr = writer.get_extra_info("peername")
    try:
        while True:
            data: bytes | None = await cautious_read(reader, timeout_seconds=5.0)
            if data is None:
                break
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()
        print(f"Connection from {addr} closed")

async def main() -> None:
    server = await asyncio.start_server(handle_client, "127.0.0.1", 8888)
    async with server:
        print("Serving with 5s read timeout...")
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
```

The `cautious_read` function wraps a single `#!py readline()` in a 5-second
timeout. If the client goes silent for too long, the read is cancelled and the
server can drop the connection. You can apply the same pattern to writes --
wrap the [`drain()`][drain] call in [`asyncio.timeout()`][asyncio-timeout] to guard against slow
consumers.

!!! warning

    A timeout on `#!py .write()` alone does nothing useful -- `#!py .write()` is
    synchronous and returns immediately. Put the timeout around [`.drain()`][drain],
    which is the coroutine that actually waits for the buffer to flush.

---

[asyncio-sleep]: https://docs.python.org/3/library/asyncio-task.html#asyncio.sleep
[await]: https://docs.python.org/3/reference/expressions.html#await
[asyncio-open-connection]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.open_connection
[drain]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.drain
[close]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.close
[wait-closed]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.wait_closed
[asyncio-streamreader]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader
[read-n]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.read
[readline]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readline
[readexactly-n]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readexactly
[asyncio-incompletereaderror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.IncompleteReadError
[readuntil-separator]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.readuntil
[at-eof]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.at_eof
[asyncio-streamwriter]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter
[write-data]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.write
[writelines-data]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.writelines
[asyncio-start-server]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.start_server
[asyncio-server]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.Server
[server-serve-forever]: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.Server.serve_forever
[taskgroup]: https://docs.python.org/3/library/asyncio-task.html#asyncio.TaskGroup
[asyncio-timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout
[official-streams]: https://docs.python.org/3/library/asyncio-stream.html
[asyncio-limitoverrunerror]: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.LimitOverrunError
