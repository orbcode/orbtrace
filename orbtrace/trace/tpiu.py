from migen import *

from litex.soc.interconnect.stream import Endpoint, Pipeline, CombinatorialActor, Converter

class Rearrange(CombinatorialActor):
    def __init__(self):
        self.sink = sink = Endpoint([('data', 128)])
        self.source = source = Endpoint([('data', 135)])

        self.comb += source.data.eq(Cat(
            sink.data[120], sink.data[1:8], sink.data[0],
            sink.data[8:16], C(0, 1),
            sink.data[121], sink.data[17:24], sink.data[16],
            sink.data[24:32], C(0, 1),
            sink.data[122], sink.data[33:40], sink.data[32],
            sink.data[40:48], C(0, 1),
            sink.data[123], sink.data[49:56], sink.data[48],
            sink.data[56:64], C(0, 1),
            sink.data[124], sink.data[65:72], sink.data[64],
            sink.data[72:80], C(0, 1),
            sink.data[125], sink.data[81:88], sink.data[80],
            sink.data[88:96], C(0, 1),
            sink.data[126], sink.data[97:104], sink.data[96],
            sink.data[104:112], C(0, 1),
            sink.data[127], sink.data[113:120], sink.data[112],
        ))

        super().__init__()

class TrackStream(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('data', 9)])
        self.source = source = Endpoint([('channel', 7), ('data', 8)])

        channel = Signal(7)
        next_channel = Signal(7)
        next_channel_valid = Signal()

        self.sync += If(sink.valid & sink.ready & next_channel_valid,
            channel.eq(next_channel),
            next_channel_valid.eq(0),
        )

        self.sync += If(sink.valid & sink.data[8],
            If(sink.data[0],
                next_channel.eq(sink.data[1:8]),
                next_channel_valid.eq(1),
            ).Else(
                channel.eq(sink.data[1:8]),
            ),
        )

        self.comb += [
            source.channel.eq(channel),
            source.data.eq(sink.data[0:8]),
            If(sink.data[8],
                sink.ready.eq(1),
            ).Else(
                sink.ready.eq(source.ready),
                source.valid.eq(sink.valid),
            ),
        ]

class Demux(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('channel', 7), ('data', 8)])
        self.source_itm = source_itm = Endpoint([('data', 8)])
        self.source_etm = source_etm = Endpoint([('data', 8)])
        
        self.comb += Case(sink.channel, {
            1: sink.connect(source_itm, omit = {'channel'}),
            2: sink.connect(source_etm, omit = {'channel'}),
            'default': sink.ready.eq(1),
        })

class StripChannelZero(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('channel', 7), ('data', 8)])
        self.source = source = Endpoint([('channel', 7), ('data', 8)])
        
        self.comb += [
            sink.connect(source),

            If(sink.channel == 0,
                sink.ready.eq(1),
                source.valid.eq(0),
            ),
        ]

class Packetizer(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('channel', 7), ('data', 8)])
        self.source = source = Endpoint([('data', 8)])

        max_size = 1024

        channel = Signal(7)
        byte_cnt = Signal(max = max_size)

        start_new_packet = Signal()

        self.comb += start_new_packet.eq((sink.channel != channel) | (byte_cnt >= max_size - 1))

        self.submodules.fsm = fsm = FSM()

        fsm.act('DATA',
            source.data.eq(sink.data),
            source.valid.eq(sink.valid & ~start_new_packet),
            sink.ready.eq(source.ready & ~start_new_packet),

            If(sink.valid & start_new_packet,
                NextState('HEADER'),
                NextValue(channel, sink.channel),
            ),

            If(sink.valid & sink.ready,
                NextValue(byte_cnt, byte_cnt + 1),
            ),
        )

        fsm.act('HEADER',
            source.data.eq(channel),
            source.first.eq(1),
            source.valid.eq(1),

            If(source.ready,
                NextState('DATA'),
                NextValue(byte_cnt, 0),
            ),
        )

class LastFromFirst(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('data', 8)])
        self.source = source = Endpoint([('data', 8)])

        data = Signal(8)
        first = Signal()
        valid = Signal()

        self.comb += [
            sink.ready.eq(~valid | (source.ready & source.valid)),

            source.data.eq(data),
            source.first.eq(first),
            source.last.eq(sink.first),
            source.valid.eq(valid & sink.valid),
        ]

        self.sync += [
            If(sink.ready & sink.valid,
                data.eq(sink.data),
                first.eq(sink.first),
                valid.eq(1),
            ),
        ]

class TPIUDemux(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('data', 128)])
        self.bypass_sink = bypass_sink = Endpoint([('data', 8)])
        self.source = source = Endpoint([('data', 8)])

        self.bypass = Signal()

        self.submodules.rearrange = Rearrange()
        self.submodules.converter = Converter(135, 9)
        self.submodules.track_stream = TrackStream()
        self.submodules.demux = Demux()
        self.submodules.strip_channel_zero = StripChannelZero()
        self.submodules.packetizer = Packetizer()
        self.submodules.last_from_first = LastFromFirst()

        self.submodules += Pipeline(
            sink,
            self.rearrange,
            self.converter,
            self.track_stream,
            #self.demux,
            self.strip_channel_zero,
        )

        self.submodules += Pipeline(
            self.packetizer,
            self.last_from_first,
            source,
        )

        self.comb += If(self.bypass,
            bypass_sink.ready.eq(self.packetizer.sink.ready),
            self.packetizer.sink.valid.eq(bypass_sink.valid),
            self.packetizer.sink.data.eq(bypass_sink.data),
            self.packetizer.sink.channel.eq(1),
        ).Else(
            self.strip_channel_zero.source.connect(self.packetizer.sink),
        )

        #self.comb += self.demux.source_etm.connect(source)
        #self.comb += self.demux.source_itm.ready.eq(1)

class TPIUSync(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('data', 8)])
        self.source = source = Endpoint([('data', 128)])
        self.reset_sync = Signal()

        buf = Signal(129, reset = 1)
        synced = Signal()

        self.comb += [
            source.valid.eq(buf[128] & synced),
            source.data.eq(buf),
            sink.ready.eq(~source.valid),
        ]

        self.sync += If(source.valid & source.ready,
            buf.eq(1),
        )

        self.sync += If(sink.valid & sink.ready,
            If(Cat(sink.data, buf)[:32] == 0xffffff7f,
                # Full sync, reset buffer.
                synced.eq(1),
                buf.eq(1),
            ).Elif(Cat(sink.data, buf)[:16] == 0xff7f,
                # Half sync, drop previous byte from buffer.
                buf.eq(buf[8:]),
            ).Else(
                # Regular byte, add to buffer.
                buf.eq(Cat(sink.data, buf)),
            )
        )

        self.sync += If(self.reset_sync,
            synced.eq(0),
        )
