from migen import *

from litex.soc.interconnect.stream import Endpoint, CombinatorialActor

class PulseLengthCapture(Module):
    def __init__(self, n_bits):
        self.source = source = Endpoint([('count', n_bits), ('level', 1)])

        self.input_signal = Signal(2)

        state = Signal(3)
        self.sync += state.eq(Cat(self.input_signal[1], self.input_signal[0], state[0]))

        add_2 = Signal()
        output_0 = Signal()
        output_1 = Signal()

        self.comb += Case(state, {
            # Two more samples equal to prev.
            0b000: add_2.eq(1),
            0b111: add_2.eq(1),

            # Two samples opposite of prev.
            0b011: output_0.eq(1),
            0b100: output_0.eq(1),

            # One sample equal to prev and one opposite.
            0b001: output_1.eq(1),
            0b110: output_1.eq(1),

            # Glitch or short pulse, ignore.
            0b010: add_2.eq(1),
            0b101: add_2.eq(1),
        })

        count = Signal(n_bits)

        self.sync += [
            source.level.eq(state[2]),
            source.valid.eq(0),

            If(add_2 & ~count[-1],
                count.eq(count + 2),
            ),

            If(output_0,
                source.count.eq(count),
                source.valid.eq(1),
                count.eq(2),
            ),

            If(output_1,
                source.count.eq(count + 1),
                source.valid.eq(1),
                count.eq(1),
            ),
        ]

class CountToByte(CombinatorialActor):
    def __init__(self, n_bits):
        self.sink = sink = Endpoint([('count', n_bits), ('level', 1)])
        self.source = source = Endpoint([('data', 8)])

        self.comb += source.data.eq(sink.count)

        super().__init__()


class ManchesterDecoder(Module):
    def __init__(self, n_bits):
        self.sink = sink = Endpoint([('count', n_bits), ('level', 1)])
        self.source = source = Endpoint([('data', 1)])

        self.submodules.fsm = fsm = FSM()

        short_threshold = Signal(n_bits) # 3/4 bit time
        long_threshold = Signal(n_bits)  # 5/4 bit time
        edge_counter   = Signal(8)       # Maximum number of edges before we force a reset (8 bytes, max 2 edges = 128 count)

        self.sync += If(source.ready & source.valid,
            source.first.eq(0),
            edge_counter.eq(edge_counter+1),
        )

        fsm.act('IDLE',
            sink.ready.eq(1),

            # Don't sync to something that's longer than we can count to (/4)
            If(sink.valid & sink.level & (sink.count[-2:]==0),
                NextState('CENTER'),
                NextValue(source.first, 1),
                NextValue(edge_counter, 0),

                # Icky fix to 'lock' 41.66MHz & 48MHz operation. This slides towards the
                # end of a bit at 48MHz but does work OK. It does _not_ work at 49MHz!!
                If (sink.count>6,
                    NextValue(short_threshold, sink.count + (sink.count >> 1)),
                    NextValue(long_threshold, ((sink.count) << 1) + (sink.count >> 1)),
                ).Else(
                    NextValue(short_threshold, 9),
                    NextValue(long_threshold, 15),
                ),                        
            ),
        )

        short = Signal()
        long = Signal()
        extra_long = Signal()
        frame_reset = Signal()

        capture = Signal()

        self.comb += [
            short.eq(sink.count <= short_threshold),
            extra_long.eq(sink.count > long_threshold),
            long.eq(~short & ~extra_long),
            frame_reset.eq(edge_counter[-1]),
        ]

        fsm.act('CENTER',
            sink.ready.eq(1),

            # Long pulse from bit center takes us to the next bit center; capture.
            If(sink.valid & long,
                capture.eq(1),
            ),

            # Short pulse from bit center takes us to bit edge.
            If(sink.valid & short,
                NextState('EDGE'),
            ),

            # Extra long pulse is either end bit or error.
            If(sink.valid & extra_long,
                NextState('IDLE'),
            ),

            # We got too many edges in this frame..reset and start again
            If(frame_reset,
                NextState('IDLE'),
            ),
        )

        fsm.act('EDGE',
            sink.ready.eq(1),

            # Short pulse from bit edge takes us to bit center; capture.
            If(sink.valid & short,
                capture.eq(1),
                NextState('CENTER'),
            ),

            # Long or extra long pulse from bit edge is either end bit or error.
            If(sink.valid & (long | extra_long),
                NextState('IDLE'),
            ),

            # We got too many edges in this frame..reset and start again
            If(frame_reset,
                NextState('IDLE'),
            ),
        )

        self.comb += If(capture,
            source.data.eq(sink.level),
            source.valid.eq(1),
        )


class BitsToBytes(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('data', 1)])
        self.source = source = Endpoint([('data', 8)])

        sr = Signal(9)

        self.comb += [
            source.valid.eq(sr[0]),
            source.data.eq(sr[1:]),
            sink.ready.eq(~source.valid),
        ]

        self.sync += [
            If(sink.valid & sink.ready,
                sr.eq(Cat(sr[1:], sink.data)),

                If(sink.first,
                    sr.eq(Cat(C(0x80, 8), sink.data)),
                ),
            ),

            If(source.valid & source.ready,
                sr.eq(0x100),
            )
        ]

class NRZDecoder(Module):
    def __init__(self, n_bits):
        self.sink = sink = Endpoint([('count', n_bits), ('level', 1)])
        self.source = source = Endpoint([('data', 1)])
        self.bitlen  = Signal(16, reset = 8000)

        acc  = Signal(n_bits + 4 + 4)

        self.comb += [
            sink.ready.eq(acc < self.bitlen),
            source.valid.eq(acc >= self.bitlen),
        ]

        self.sync += [
            # No bits left in accumulator, receive a new count.
            If(sink.ready & sink.valid,
                acc.eq((sink.count << 4) + (self.bitlen >> 1)),
                source.data.eq(sink.level),
            ).Elif(source.valid & source.ready,
                acc.eq(acc - self.bitlen), # Subtract one bit length.
            )
        ]

class UARTDecoder(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('data', 1)])
        self.source = source = Endpoint([('data', 8)])

        self.submodules.fsm = fsm = FSM()

        sr = Signal(10)

        self.comb += [
            source.valid.eq(sr[0] & sr[9]),
            source.data.eq(sr[1:]),
            sink.ready.eq(~source.valid),
        ]

        fsm.act('WAITSTART',
            If(sink.valid & sink.ready & (sink.data == 0),
                NextValue(sr, 0x200),
                NextState('GETBITS'),
            ),
        )

        fsm.act('GETBITS',
            If((sink.valid & sink.ready),
                NextValue(sr, Cat(sr[1:], sink.data)),
            ),
            If (sr[0],
                NextState('WAITSTART'),
            ),
        )

        self.sync += [
            If(source.valid & source.ready,
                sr.eq(0x200),
            )
        ]
