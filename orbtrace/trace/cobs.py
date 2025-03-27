from amaranth import *
from amaranth.lib import wiring, stream

from ..stream import Packet, SyncFIFOBuffered

class GroupSplitter(wiring.Component):
    input: wiring.In(stream.Signature(Packet(has_last = True)))
    output_len: wiring.Out(stream.Signature(Packet(has_last = True)))
    output_data: wiring.Out(stream.Signature(8))

    def __init__(self, delimiter = 0):
        super().__init__()
        self.delimiter = delimiter

    def elaborate(self, platform):
        m = Module()

        cnt = Signal(8)
        cnt_inc = Signal()
        cnt_reset = Signal()

        last = Signal()

        m.d.comb += [
            self.input.ready.eq(self.output_data.ready & self.output_len.ready & (cnt < 254) & ~last),
            self.output_data.payload.eq(self.input.payload.data),
            self.output_len.payload.data.eq(cnt),
            self.output_len.payload.last.eq(last),
        ]

        with m.If((self.input.ready & self.input.valid) | (cnt == 254) | last):
            with m.If((self.input.payload.data == self.delimiter) | (cnt == 254) | last):
                m.d.comb += [
                    self.output_len.valid.eq(1),
                    cnt_reset.eq(self.output_len.ready),
                ]
            with m.If((self.input.payload.data != self.delimiter) & (cnt < 254) & ~last):
                m.d.comb += [
                    self.output_data.valid.eq(1),
                    cnt_inc.eq(1),
                ]

        with m.If(cnt_inc):
            m.d.sync += cnt.eq(cnt + 1)
        with m.If(cnt_reset):
            m.d.sync += cnt.eq(self.output_data.valid)
        with m.If(self.input.ready & self.input.valid & self.input.payload.last):
            m.d.sync += last.eq(1)
        with m.If(self.output_len.ready & last):
            m.d.sync += last.eq(0)

        return m

class GroupCombiner(wiring.Component):
    input_data: wiring.In(stream.Signature(8))
    input_len: wiring.In(stream.Signature(Packet(has_last = True)))
    output: wiring.Out(stream.Signature(Packet(has_last = True)))

    def __init__(self, delimiter = 0):
        super().__init__()
        self.delimiter = delimiter

    def elaborate(self, platform):
        m = Module()

        header = Signal(8)
        cnt = Signal(8)
        last = Signal()

        m.d.comb += header.eq(self.input_len.payload.data),
        with m.If(self.input_len.payload.data >= self.delimiter):
            m.d.comb += header.eq(self.input_len.payload.data + 1),

        with m.FSM() as fsm:
            with m.State('HEADER'):
                m.d.comb += [
                    self.input_len.ready.eq(self.output.ready),
                    self.output.valid.eq(self.input_len.valid),
                    self.output.payload.last.eq(self.input_len.payload.last & (self.input_len.payload.data == 0)),
                    self.output.payload.data.eq(header),
                ]

                with m.If(self.output.ready & self.output.valid & (self.input_len.payload.data > 0)):
                    m.next = 'DATA'
                    m.d.sync += [
                        cnt.eq(self.input_len.payload.data - 1),
                        last.eq(self.input_len.payload.last),
                    ]

            with m.State('DATA'):
                m.d.comb += [
                    self.input_data.ready.eq(self.output.ready),
                    self.output.valid.eq(self.input_data.valid),
                    self.output.payload.last.eq(last & (cnt == 0)),
                    self.output.payload.data.eq(self.input_data.payload),
                ]

                with m.If(self.output.ready & self.output.valid):
                    m.d.sync += cnt.eq(cnt - 1)
                    with m.If(cnt == 0):
                        m.next = 'HEADER'

        return m

class DelimiterAppender(wiring.Component):
    input: wiring.In(stream.Signature(Packet(has_last = True)))
    output: wiring.Out(stream.Signature(Packet(has_last = True)))

    def __init__(self, delimiter = 0):
        super().__init__()
        self.delimiter = delimiter

    def elaborate(self, platform):
        m = Module()

        with m.FSM() as fsm:
            with m.State('DATA'):
                m.d.comb += [
                    self.input.ready.eq(self.output.ready),
                    self.output.valid.eq(self.input.valid),
                    self.output.payload.data.eq(self.input.payload),
                ]

                with m.If(self.input.valid & self.input.ready & self.input.payload.last):
                    m.next = 'DELIMITER'

            with m.State('DELIMITER'):
                m.d.comb += [
                    self.output.valid.eq(1),
                    self.output.payload.data.eq(self.delimiter),
                    self.output.payload.last.eq(1),
                ]

                with m.If(self.output.ready):
                    m.next = 'DATA'

        return m

class COBSEncoder(wiring.Component):
    input: wiring.In(stream.Signature(Packet(has_last = True)))
    output: wiring.Out(stream.Signature(Packet(has_last = True)))

    def __init__(self, *, delimiter = 0, append_delimiter = False):
        super().__init__()
        self.delimiter = delimiter
        self.append_delimiter = append_delimiter

    def elaborate(self, platform):
        m = Module()

        m.submodules.group_splitter = group_splitter = GroupSplitter(self.delimiter)
        m.submodules.fifo_len = fifo_len = SyncFIFOBuffered(Packet(has_last = True), 256)
        m.submodules.fifo_data = fifo_data = SyncFIFOBuffered(8, 256)
        m.submodules.group_combiner = group_combiner = GroupCombiner(self.delimiter)

        wiring.connect(m, wiring.flipped(self.input), group_splitter.input)
        wiring.connect(m, group_splitter.output_len, fifo_len.input)
        wiring.connect(m, group_splitter.output_data, fifo_data.input)
        wiring.connect(m, fifo_len.output, group_combiner.input_len)
        wiring.connect(m, fifo_data.output, group_combiner.input_data)

        if self.append_delimiter:
            m.submodules.delimiter_appender = delimiter_appender = DelimiterAppender(self.delimiter)
            wiring.connect(m, group_combiner.output, delimiter_appender.input)
            wiring.connect(m, delimiter_appender.output, wiring.flipped(self.output))
        else:
            wiring.connect(m, group_combiner.output, wiring.flipped(self.output))

        m.d.sync += Signal().eq(1)

        return m
