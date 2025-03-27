from amaranth import *
from amaranth.lib import wiring, stream, data

from ..stream import Packet, Serializer

PulseLength = data.StructLayout({'level': 1, 'count': 16})

class PulseLengthCapture(wiring.Component):
    input: wiring.In(2)
    output: wiring.Out(stream.Signature(PulseLength))

    def elaborate(self, platform):
        m = Module()

        state = Signal(3)
        m.d.sync += state.eq(Cat(self.input[1], self.input[0], state[0]))

        add_2 = Signal()
        output_0 = Signal()
        output_1 = Signal()

        with m.Switch(state):
            # Two more samples equal to prev.
            with m.Case(0b000, 0b111):
                m.d.comb += add_2.eq(1)

            # Two samples opposite of prev.
            with m.Case(0b011, 0b100):
                m.d.comb += output_0.eq(1)

            # One sample equal to prev and one opposite.
            with m.Case(0b001, 0b110):
                m.d.comb += output_1.eq(1)

            # Glitch or short pulse, ignore.
            with m.Case(0b010, 0b101):
                m.d.comb += add_2.eq(1)

        count = Signal(16)

        m.d.sync += [
            self.output.payload.level.eq(state[2]),
            self.output.valid.eq(0),
        ]

        with m.If(count[-1]):
            m.d.sync += [
                self.output.payload.count.eq(count),
                self.output.valid.eq(1),
                count.eq(0),
            ]

        with m.If(add_2 & ~count[-1]):
            m.d.sync += [
                count.eq(count + 2),
            ]

        with m.If(output_0):
            m.d.sync += [
                self.output.payload.count.eq(count),
                self.output.valid.eq(1),
                count.eq(2),
            ]

        with m.If(output_1):
            m.d.sync += [
                self.output.payload.count.eq(count + 1),
                self.output.valid.eq(1),
                count.eq(1),
            ]

        return m

class ManchesterDecoder(wiring.Component):
    input: wiring.In(stream.Signature(PulseLength))
    output: wiring.Out(stream.Signature(Packet(1, has_first = True)))

    def elaborate(self, platform):
        m = Module()

        short_threshold = Signal(16) # 3/4 bit time
        long_threshold = Signal(16)  # 5/4 bit time
        edge_counter = Signal(8)     # Maximum number of edges before we force a reset (8 bytes, max 2 edges = 128 count)

        with m.If(self.output.ready & self.output.valid):
            m.d.sync += [
                self.output.payload.first.eq(0),
                edge_counter.eq(edge_counter + 1),
            ]

        short = Signal()
        long = Signal()
        extra_long = Signal()
        frame_reset = Signal()

        capture = Signal()

        m.d.comb += [
            short.eq(self.input.payload.count <= short_threshold),
            extra_long.eq(self.input.payload.count > long_threshold),
            long.eq(~short & ~extra_long),
            frame_reset.eq(edge_counter[-1]),
        ]

        with m.FSM() as fsm:
            with m.State('IDLE'):
                m.d.comb += self.input.ready.eq(1)

                # Don't sync to something that's longer than we can count to (/4)
                with m.If(self.input.valid & self.input.payload.level & (self.input.payload.count[-2:] == 0)):
                    m.next = 'CENTER'
                    m.d.sync += [
                        self.output.payload.first.eq(1),
                        edge_counter.eq(0),
                    ]

                    # Icky fix to 'lock' 41.66MHz & 48MHz operation. This slides towards the
                    # end of a bit at 48MHz but does work OK. It does _not_ work at 49MHz!!
                    with m.If(self.input.payload.count > 6):
                        m.d.sync += [
                            short_threshold.eq(self.input.payload.count + (self.input.payload.count >> 1)),
                            long_threshold.eq((self.input.payload.count << 1) + (self.input.payload.count >> 1)),
                        ]
                    with m.Else():
                        m.d.sync += [
                            short_threshold.eq(8),
                            long_threshold.eq(14),
                        ]

            with m.State('CENTER'):
                m.d.comb += self.input.ready.eq(1)

                # Long pulse from bit center takes us to the next bit center; capture.
                with m.If(self.input.valid & long):
                    m.d.comb += capture.eq(1)

                # Short pulse from bit center takes us to bit edge.
                with m.If(self.input.valid & short):
                    m.next = 'EDGE'

                # Extra long pulse is either end bit or error.
                with m.If(self.input.valid & extra_long):
                    m.next = 'IDLE'

                # We got too many edges in this frame..reset and start again
                with m.If(frame_reset):
                    m.next = 'IDLE'

            with m.State('EDGE'):
                m.d.comb += self.input.ready.eq(1)

                # Short pulse from bit edge takes us to bit center; capture.
                with m.If(self.input.valid & short):
                    m.d.comb += capture.eq(1)
                    m.next = 'CENTER'

                # Long or extra long pulse from bit edge is either end bit or error.
                with m.If(self.input.valid & (long | extra_long)):
                    m.next = 'IDLE'

                # We got too many edges in this frame..reset and start again
                with m.If(frame_reset):
                    m.next = 'IDLE'

        with m.If(capture):
            m.d.comb += [
                self.output.payload.data.eq(self.input.payload.level),
                self.output.valid.eq(1),
            ]

        return m

class BitsToBytes(wiring.Component):
    input: wiring.In(stream.Signature(Packet(1, has_first = True)))
    output: wiring.Out(stream.Signature(8))

    def elaborate(self, platform):
        m = Module()

        sr = Signal(9)

        m.d.comb += [
            self.output.valid.eq(sr[0]),
            self.output.payload.eq(sr[1:]),
            self.input.ready.eq(~self.output.valid),
        ]

        with m.If(self.input.valid & self.input.ready):
            m.d.sync += sr.eq(Cat(sr[1:], self.input.payload.data))

            with m.If(self.input.payload.first):
                m.d.sync += sr.eq(Cat(C(0x80, 8), self.input.payload.data))

        with m.If(self.output.valid & self.output.ready):
            m.d.sync += sr.eq(0x100)

        return m

class NRZDecoder(wiring.Component):
    input: wiring.In(stream.Signature(PulseLength))
    output: wiring.Out(stream.Signature(1))

    bitlen: wiring.In(16, init = 8000)

    def elaborate(self, platform):
        m = Module()

        acc = Signal(PulseLength['count'].width + 4 + 4)
        cnt = Signal(4)

        m.d.comb += [
            self.output.valid.eq((acc >= self.bitlen) & (cnt < 12)),
            self.input.ready.eq(~self.output.valid),
        ]

        # No bits left in accumulator, receive a new count.
        with m.If(self.input.valid & self.input.ready):
            m.d.sync += [
                acc.eq((self.input.payload.count << 4) + (self.bitlen >> 1)),
                self.output.payload.eq(self.input.payload.level),
                cnt.eq(0),
            ]

        with m.Elif(self.output.valid & self.output.ready):
            m.d.sync += [
                acc.eq(acc - self.bitlen), # Subtract one bit length.
                cnt.eq(cnt + 1),
            ]

        return m

class UARTDecoder(wiring.Component):
    input: wiring.In(stream.Signature(1))
    output: wiring.Out(stream.Signature(8))

    def elaborate(self, platform):
        m = Module()

        sr = Signal(10)

        m.d.comb += [
            self.output.valid.eq(sr[0] & sr[9]),
            self.output.payload.eq(sr[1:]),
            self.input.ready.eq(~self.output.valid),
        ]

        with m.FSM() as fsm:
            with m.State('WAITSTART'):
                with m.If(self.input.valid & self.input.ready & (self.input.payload == 0)):
                    m.d.sync += sr.eq(0x200)
                    m.next = 'GETBITS'

            with m.State('GETBITS'):
                with m.If(self.input.valid & self.input.ready):
                    m.d.sync += sr.eq(Cat(sr[1:], self.input.payload))

                with m.If(sr[0]):
                    m.next = 'WAITSTART'

        with m.If(self.output.valid & self.output.ready):
            m.d.sync += sr.eq(0x200)

        return m
