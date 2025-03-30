from amaranth import *
from amaranth.lib import wiring, stream, data

from ..stream import Packet, Serializer

TPIURawFrame = data.ArrayLayout(8, 16)

TPIUUnmangledByte = data.StructLayout({'data': 8, 'is_id': 1})
TPIUUnmangledFrame = data.ArrayLayout(TPIUUnmangledByte, 15)

MuxedByte = data.StructLayout({'data': 8, 'channel': 7})

class TPIUSync(wiring.Component):
    input: wiring.In(stream.Signature(8))
    output: wiring.Out(stream.Signature(TPIURawFrame))
    reset_sync: wiring.In(1)

    def elaborate(self, platform):
        m = Module()

        buf = Signal(129, init = 1)
        synced = Signal()

        m.d.comb += [
            self.output.payload.eq(buf),
            self.output.valid.eq(buf[128] & synced),
            self.input.ready.eq(~self.output.valid),
        ]

        for byte, bit in zip(range(16), reversed(range(0, 128, 8))):
            m.d.comb += self.output.payload[byte].eq(buf[bit:bit + 8])

        with m.If(self.output.valid & self.output.ready):
            m.d.sync += buf.eq(1)

        with m.If(self.input.valid & self.input.ready):
            with m.If(Cat(self.input.payload, buf)[:32] == 0xffffff7f):
                m.d.sync += [
                    synced.eq(1),
                    buf.eq(1),
                ]
            with m.Elif(Cat(self.input.payload, buf)[:16] == 0xff7f):
                m.d.sync += buf.eq(buf[8:])
            with m.Else():
                m.d.sync += buf.eq(Cat(self.input.payload, buf))

        with m.If(self.reset_sync):
            m.d.sync += synced.eq(0)

        return m

class Unmangle(wiring.Component):
    input: wiring.In(stream.Signature(TPIURawFrame))
    output: wiring.Out(stream.Signature(TPIUUnmangledFrame))

    def elaborate(self, platform):
        m = Module()

        m.d.comb += [
            self.output.valid.eq(self.input.valid),
            self.input.ready.eq(self.output.ready),
        ]

        for i in range(15):
            if i & 1 == 0:
                m.d.comb += self.output.payload[i].is_id.eq(self.input.payload[i][0])
                m.d.comb += self.output.payload[i].data.eq(Cat(self.input.payload[15][i // 2], self.input.payload[i][1:]))
            else:
                m.d.comb += self.output.payload[i].data.eq(self.input.payload[i])

        return m

class TrackStream(wiring.Component):
    input: wiring.In(stream.Signature(TPIUUnmangledByte))
    output: wiring.Out(stream.Signature(MuxedByte))

    def elaborate(self, platform):
        m = Module()

        channel = Signal(7)
        next_channel = Signal(7)
        next_channel_valid = Signal()

        m.d.comb += [
            self.input.ready.eq(self.output.ready),
            self.output.valid.eq(self.input.valid & ~self.input.payload.is_id),
            self.output.payload.data.eq(self.input.payload.data),
            self.output.payload.channel.eq(channel),
        ]

        with m.If(self.input.valid & self.input.payload.is_id):
            with m.If(self.input.payload.data[0]):
                m.d.sync += [
                    next_channel.eq(self.input.payload.data[1:]),
                    next_channel_valid.eq(1),
                ]
            with m.Else():
                m.d.sync += channel.eq(self.input.payload.data[1:])

        with m.If(self.output.valid & self.output.ready & next_channel_valid):
            m.d.sync += [
                channel.eq(next_channel),
                next_channel_valid.eq(0),
            ]

        return m

class StripChannelZero(wiring.Component):
    input: wiring.In(stream.Signature(MuxedByte))
    output: wiring.Out(stream.Signature(MuxedByte))

    def elaborate(self, platform):
        m = Module()

        m.d.comb += [
            self.input.ready.eq(self.output.ready),
            self.output.valid.eq(self.input.valid & (self.input.payload.channel != 0)),
            self.output.payload.eq(self.input.payload),
        ]

        return m

class Packetizer(wiring.Component):
    input: wiring.In(stream.Signature(MuxedByte))
    output: wiring.Out(stream.Signature(Packet(has_last = True)))

    def __init__(self, timeout = 7_500_000):
        super().__init__()
        self.timeout = timeout

    def elaborate(self, platform):
        m = Module()

        max_size = 1024

        channel = Signal(7)
        data = Signal(8)
        byte_cnt = Signal(range(max_size))
        timeout_cnt = Signal(range(self.timeout + 1))

        start_new_packet = Signal()

        m.d.comb += start_new_packet.eq(
            (self.input.valid & (self.input.payload.channel != channel)) |
            (byte_cnt >= max_size - 1) |
            (timeout_cnt == 0))

        with m.If(timeout_cnt):
            m.d.sync += timeout_cnt.eq(timeout_cnt - 1)

        with m.If(self.input.valid):
            m.d.sync += timeout_cnt.eq(self.timeout)

        with m.FSM() as fsm:
            with m.State('HEADER'):
                m.d.comb += [
                    self.output.payload.data.eq(self.input.payload.channel),
                    #self.output.payload.first.eq(1),
                    self.output.valid.eq(self.input.valid),
                    self.input.ready.eq(self.output.ready),
                ]

                with m.If(self.input.valid & self.output.ready):
                    m.next = 'DATA'
                    m.d.sync += [
                        channel.eq(self.input.payload.channel),
                        byte_cnt.eq(0),
                        data.eq(self.input.payload.data),
                    ]

            with m.State('DATA'):
                m.d.comb += [
                    self.output.payload.data.eq(data),
                    self.output.valid.eq(self.input.valid),
                    self.input.ready.eq(self.output.ready),
                ]

                with m.If(start_new_packet):
                    m.d.comb += [
                        self.output.valid.eq(0),
                        self.input.ready.eq(0),
                    ]
                    m.next = 'END'

                with m.If(self.input.valid & self.input.ready):
                    m.d.sync += [
                        data.eq(self.input.payload.data),
                        byte_cnt.eq(byte_cnt + 1),
                    ]

            with m.State('END'):
                m.d.comb += [
                    self.output.payload.data.eq(data),
                    self.output.payload.last.eq(1),
                    self.output.valid.eq(1),
                ]

                with m.If(self.output.ready):
                    m.next = 'HEADER'

        return m

class TPIUDemux(wiring.Component):
    input: wiring.In(stream.Signature(TPIURawFrame))
    input_bypass: wiring.In(stream.Signature(8))
    output: wiring.Out(stream.Signature(Packet(has_last = True)))

    bypass: wiring.In(1)

    def __init__(self, timeout = 7_500_000):
        super().__init__()
        self.timeout = timeout

    def elaborate(self, platform):
        m = Module()

        m.submodules.unmangle = unmangle = Unmangle()
        m.submodules.serializer = serializer = Serializer(TPIUUnmangledFrame)
        m.submodules.track_stream = track_stream = TrackStream()
        m.submodules.strip_channel_zero = strip_channel_zero = StripChannelZero()
        m.submodules.packetizer = packetizer = Packetizer(timeout = self.timeout)

        wiring.connect(m, wiring.flipped(self.input), unmangle.input)
        wiring.connect(m, unmangle.output, serializer.input)
        wiring.connect(m, serializer.output, track_stream.input)
        wiring.connect(m, track_stream.output, strip_channel_zero.input)

        with m.If(self.bypass):
            m.d.comb += [
                self.input_bypass.ready.eq(packetizer.input.ready),
                packetizer.input.valid.eq(self.input_bypass.valid),
                packetizer.input.payload.data.eq(self.input_bypass.payload),
                packetizer.input.payload.channel.eq(1),
            ]
        with m.Else():
            wiring.connect(m, strip_channel_zero.output, packetizer.input)

        wiring.connect(m, packetizer.output, wiring.flipped(self.output))

        return m
