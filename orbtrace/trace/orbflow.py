from amaranth import *
from amaranth.lib import wiring, stream

from ..stream import Packet

class ChecksumAppender(wiring.Component):
    input: wiring.In(stream.Signature(Packet(has_last = True)))
    output: wiring.Out(stream.Signature(Packet(has_last = True)))

    def elaborate(self, platform):
        m = Module()

        checksum = Signal(8)

        with m.FSM() as fsm:
            with m.State('DATA'):
                m.d.comb += [
                    self.input.ready.eq(self.output.ready),
                    self.output.valid.eq(self.input.valid),
                    self.output.payload.data.eq(self.input.payload.data),
                ]

                with m.If(self.input.valid & self.input.ready):
                    m.d.sync += checksum.eq(checksum - self.input.payload.data)

                    with m.If(self.input.payload.last):
                        m.next = 'CHECKSUM'

            with m.State('CHECKSUM'):
                m.d.comb += [
                    self.output.valid.eq(1),
                    self.output.payload.data.eq(checksum),
                    self.output.payload.last.eq(1),
                ]

                with m.If(self.output.ready):
                    m.next = 'DATA'
                    m.d.sync += checksum.eq(0)

        return m

class SuperFramer(wiring.Component):
    input: wiring.In(stream.Signature(Packet(has_last = True)))
    output: wiring.Out(stream.Signature(Packet(has_last = True)))

    def __init__(self, interval, threshold):
        super().__init__()
        self.interval = interval
        self.threshold = threshold

    def elaborate(self, platform):
        m = Module()

        interval_cnt = Signal(range(self.interval + 1))
        byte_cnt = Signal(range(self.threshold + 1))

        flush = Signal()

        data = Signal(8)
        last = Signal()
        valid = Signal()

        m.d.comb += [
            self.input.ready.eq(~valid | (self.output.ready & self.output.valid)),

            self.output.payload.data.eq(data),
            self.output.payload.last.eq(last & flush),
            self.output.valid.eq(valid & (self.input.valid | flush)),
        ]

        with m.If(self.output.ready & self.output.valid):
            m.d.sync += [
                valid.eq(0),
            ]

            with m.If(last & flush):
                m.d.sync += flush.eq(0)

            with m.If(byte_cnt < self.threshold):
                m.d.sync += byte_cnt.eq(byte_cnt + 1)

        with m.If(self.input.ready & self.input.valid):
            m.d.sync += [
                data.eq(self.input.payload.data),
                last.eq(self.input.payload.last),
                valid.eq(1),
            ]

        with m.If(valid & (interval_cnt < self.interval)):
            m.d.sync += interval_cnt.eq(interval_cnt + 1)

        with m.If(interval_cnt == self.interval):
            m.d.sync += [
                byte_cnt.eq(0),
                interval_cnt.eq(0),
            ]

            with m.If(byte_cnt < self.threshold):
                m.d.sync += flush.eq(1)

        return m
