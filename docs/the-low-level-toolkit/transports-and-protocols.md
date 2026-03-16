---
title: Transports and Protocols
description: >-
  An orientation to asyncio's transport/protocol layer. Learn when to stay
  with streams, when to drop lower, what the model looks like, and where to
  rely on the official docs for the full API.
---

# Transports and Protocols

For most application code, stop at
[Streams](../beyond-the-basics/streams.md). That is the default.

This section exists for the moment when you need to understand what sits under
streams, or when you are writing library code that genuinely needs the lower
layer. It is intentionally an overview, not a second reference manual.

## Stay With Streams Unless You Need One of These

Drop below streams only when you need something like:

- callback-driven integration with another subsystem
- tighter control over buffering or flow control
- a protocol implementation that already thinks in callbacks and bytes
- lower overhead than a coroutine per connection step

If your use case is just "open a TCP connection, read bytes, write bytes",
streams are the better teaching and maintenance choice.

## The Model in One Sentence

- the **transport** moves bytes
- the **protocol** reacts to events about those bytes

That is the split.

When a connection is created, asyncio wires one transport to one protocol. The
transport calls protocol callbacks such as [`connection_made()`][connection-made] and
[`data_received()`][data-received]. The protocol calls transport methods such as [`write()`][write] and
[`close()`][close].

## Minimal Shape

```python
import asyncio


class EchoProtocol(asyncio.Protocol):
    def connection_made(self, transport: asyncio.Transport) -> None:
        self.transport = transport

    def data_received(self, data: bytes) -> None:
        self.transport.write(data)


async def main() -> None:
    loop = asyncio.get_running_loop()
    server = await loop.create_server(EchoProtocol, "127.0.0.1", 8888)
    async with server:
        await server.serve_forever()
```

That example is deliberately tiny because the core lesson is the shape, not the
complete API.

## Main Differences From Streams

- there is no [`await reader.read(...)`][await-reader-read-etc]
- there is no [`await writer.drain()`][await-writer-drain]
- you react to callbacks instead of suspending coroutines
- you own more of the buffering and message-framing story yourself

That last point matters. [`data_received()`][data-received] gives you chunks of bytes, not
application-level messages. Framing is your job.

## Flow Control Still Matters

The lower layer gives you explicit flow-control hooks such as
[`pause_reading()`][pause-reading], [`resume_reading()`][resume-reading], [`pause_writing()`][pause-writing], and
[`resume_writing()`][resume-writing].

That power is useful, but it is also why the official docs are the right place
to go next if you decide to work at this level.

## What to Read Next

- Full reference: [Transports and Protocols][transports-and-protocols]
- Loop APIs that construct this layer: [Event Loop][event-loop]
- High-level alternative: [Streams](../beyond-the-basics/streams.md)

[transports-and-protocols]: https://docs.python.org/3/library/asyncio-protocol.html
[event-loop]: https://docs.python.org/3/library/asyncio-eventloop.html
[connection-made]: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseProtocol.connection_made
[pause-reading]: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.ReadTransport.pause_reading
[data-received]: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.Protocol.data_received
[await-reader-read-etc]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.read
[await-writer-drain]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.drain
[pause-writing]: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseProtocol.pause_writing
[close]: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseTransport.close
[write]: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.WriteTransport.write
[resume-writing]: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseProtocol.resume_writing
[resume-reading]: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.ReadTransport.resume_reading
