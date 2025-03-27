from amaranth.sim import SimulatorContext

from orbtrace.stream import Packet

async def stream_put(ctx: SimulatorContext, stream, payload):
    ctx.set(stream.valid, 1)
    ctx.set(stream.payload, payload)

    await ctx.tick().until(stream.ready == 1)

    ctx.set(stream.valid, 0)

async def stream_get(ctx: SimulatorContext, stream):
    ctx.set(stream.ready, 1)

    payload, = await ctx.tick().sample(stream.payload).until(stream.valid == 1)

    ctx.set(stream.ready, 0)
    return payload

async def send_packet(ctx: SimulatorContext, stream, packet):
    shape = stream.payload.shape()
    assert isinstance(shape, Packet)

    ctx.set(stream.valid, 1)
    if shape.has_first:
        ctx.set(stream.payload.first, 1)

    for i, e in enumerate(packet):
        ctx.set(stream.payload.data, e)
        if shape.has_last:
            ctx.set(stream.payload.last, i == len(packet) - 1)

        await ctx.tick().until(stream.ready == 1)

    ctx.set(stream.valid, 0)

async def recv_packet(ctx: SimulatorContext, stream):
    shape = stream.payload.shape()
    assert isinstance(shape, Packet)
    assert shape.has_last

    buf = []

    ctx.set(stream.ready, 1)

    while True:
        payload, = await ctx.tick().sample(stream.payload).until(stream.valid == 1)
        buf.append(payload.data)

        if payload.last:
            break

    ctx.set(stream.ready, 0)

    return buf
