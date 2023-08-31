from migen import *

from litex.soc.interconnect import stream

class GroupSplitter(Module):
    def __init__(self, delimiter = 0):
        self.sink = sink = stream.Endpoint([('data', 8)])
        self.source_data = source_data = stream.Endpoint([('data', 8)])
        self.source_len = source_len = stream.Endpoint([('len', 8)])

        cnt = Signal(8)
        cnt_inc = Signal()
        cnt_reset = Signal()

        last = Signal()

        self.comb += [
            sink.ready.eq(source_data.ready & source_len.ready & (cnt < 254) & ~last),
            source_data.data.eq(sink.data),
            source_len.len.eq(cnt),
            source_len.last.eq(last),

            If((sink.ready & sink.valid) | (cnt == 254) | last,
                If((sink.data == delimiter) | (cnt == 254) | last,
                    source_len.valid.eq(1),
                    cnt_reset.eq(source_len.ready),
                ),
                If((sink.data != delimiter) & (cnt < 254) & ~last,
                    source_data.valid.eq(1),
                    cnt_inc.eq(1),
                ),
            ),
        ]

        self.sync += [
            If(cnt_inc,
                cnt.eq(cnt + 1),
            ),
            If(cnt_reset,
                cnt.eq(source_data.valid),
            ),
            If(sink.ready & sink.valid & sink.last,
                last.eq(1),
            ),
            If(source_len.ready & last,
                last.eq(0),
            ),
        ]

class GroupCombiner(Module):
    def __init__(self, delimiter = 0):
        self.sink_data = sink_data = stream.Endpoint([('data', 8)])
        self.sink_len = sink_len = stream.Endpoint([('len', 8)])
        self.source = source = stream.Endpoint([('data', 8)])

        self.submodules.fsm = fsm = FSM()

        header = Signal(8)
        cnt = Signal(8)
        last = Signal()

        self.comb += [
            header.eq(sink_len.len),
            If(sink_len.len >= delimiter,
                header.eq(sink_len.len + 1),
            ),
        ]

        fsm.act('HEADER',
            sink_len.ready.eq(source.ready),
            source.valid.eq(sink_len.valid),
            source.last.eq(sink_len.last & (sink_len.len == 0)),
            source.data.eq(header),

            If(source.ready & source.valid & (sink_len.len > 0),
                NextState('DATA'),
                NextValue(cnt, sink_len.len - 1),
                NextValue(last, sink_len.last),
            ),
        )

        fsm.act('DATA',
            sink_data.ready.eq(source.ready),
            source.valid.eq(sink_data.valid),
            source.last.eq(last & (cnt == 0)),
            source.data.eq(sink_data.data),

            If(source.ready & source.valid,
                NextValue(cnt, cnt - 1),

                If(cnt == 0,
                    NextState('HEADER'),
                ),
            ),
        )

class COBSEncoder(Module):
    def __init__(self, delimiter = 0):
        self.sink = stream.Endpoint([('data', 8)])
        self.source = stream.Endpoint([('data', 8)])

        self.submodules.group_splitter = GroupSplitter(delimiter)
        self.submodules.fifo_data = stream.SyncFIFO([('data', 8)], 256)
        self.submodules.fifo_len = stream.SyncFIFO([('len', 8)], 256)
        self.submodules.group_combiner = GroupCombiner(delimiter)

        self.comb += [
            self.sink.connect(self.group_splitter.sink),

            self.group_splitter.source_data.connect(self.fifo_data.sink),
            self.group_splitter.source_len.connect(self.fifo_len.sink),

            self.fifo_data.source.connect(self.group_combiner.sink_data),
            self.fifo_len.source.connect(self.group_combiner.sink_len),

            self.group_combiner.source.connect(self.source),
        ]

class DelimiterAppender(Module):
    def __init__(self, delimiter = 0):
        self.sink = stream.Endpoint([('data', 8)])
        self.source = stream.Endpoint([('data', 8)])

        self.submodules.fsm = fsm = FSM()

        fsm.act('DATA',
            self.sink.connect(self.source, omit = {'last'}),

            If(self.sink.valid & self.sink.ready & self.sink.last,
                NextState('DELIMITER'),
            ),
        )

        fsm.act('DELIMITER',
            self.source.data.eq(delimiter),
            self.source.last.eq(1),
            self.source.valid.eq(1),

            If(self.source.ready,
                NextState('DATA'),
            ),
        )

class SuperFramer(Module):
    def __init__(self, interval, threshold):
        self.sink = sink = stream.Endpoint([('data', 8)])
        self.source = source = stream.Endpoint([('data', 8)])

        interval_cnt = Signal(max = interval + 1)
        byte_cnt = Signal(max = threshold + 1)

        flush = Signal()

        data = Signal(8)
        first = Signal(reset = 1)
        last = Signal()
        valid = Signal()

        self.comb += [
            sink.ready.eq(~valid | (source.ready & source.valid)),

            source.data.eq(data),
            source.first.eq(first),
            source.last.eq(last & flush),
            source.valid.eq(valid & (sink.valid | flush)),
        ]

        self.sync += [
            If(source.ready & source.valid,
                first.eq(source.last),
                valid.eq(0),

                If(last & flush,
                    flush.eq(0),
                ),

                If(byte_cnt < threshold,
                    byte_cnt.eq(byte_cnt + 1),
                ),
            ),

            If(sink.ready & sink.valid,
                data.eq(sink.data),
                last.eq(sink.last),
                valid.eq(1),
            ),

            If(valid & (interval_cnt < interval),
                interval_cnt.eq(interval_cnt + 1),
            ),

            If(interval_cnt == interval,
                byte_cnt.eq(0),
                interval_cnt.eq(0),

                If(byte_cnt < threshold,
                    flush.eq(1),
                ),
            ),
        ]
