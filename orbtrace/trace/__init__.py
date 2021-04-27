from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.stream import Endpoint, AsyncFIFO, Pipeline, CombinatorialActor
from litex.build.io import DDRInput

class TracePHY(Module):
    def __init__(self, pads):
        self.source = source = Endpoint([('data', 128)])

        traceclk = Signal()
        tracedata = Signal(4)

        self.comb += [
            traceclk.eq(pads.clk),
            tracedata.eq(pads.data),
        ]

        trace_a = Signal(4)
        trace_b = Signal(4)

        for i in range(4):
            self.specials += DDRInput(
                clk = traceclk,
                i = tracedata[i],
                o1 = trace_a[i],
                o2 = trace_b[i],
            )

        self.comb += ClockSignal().eq(traceclk)

        width = Signal(2)

        self.comb += width.eq(3)

        edgeOutput = Signal()

        fravail = Signal()
        fravail_last = Signal()
        frame = Signal(128)

        self.sync += fravail_last.eq(fravail)

        self.comb += [
            source.data.eq(frame),
            source.valid.eq(fravail != fravail_last),
            #source.first.eq(1),
            #source.last.eq(1),
        ]

        traceif = Instance('traceIF',
            i_rst = ResetSignal(),
            i_traceDina = trace_a,
            i_traceDinb = trace_b,
            i_traceClkin = traceclk,
            i_width = width,
            o_edgeOutput = edgeOutput,

            o_FrAvail = fravail,
            o_Frame = frame,
        )

        self.specials += traceif

def byteswap(signal):
    assert len(signal) % 8 == 0

    return Cat(signal[i:i+8] for i in reversed(range(0, len(signal), 8)))

class ByteSwap(CombinatorialActor):
    def __init__(self, num_bytes):
        self.sink = sink = Endpoint([('data', 8 * num_bytes)])
        self.source = source = Endpoint([('data', 8 * num_bytes)])

        self.comb += source.data.eq(byteswap(sink.data))

        super().__init__()

class Injector(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('data', 128)])
        self.sink_inject = sink_inject = Endpoint([('data', 128)])
        self.source = source = Endpoint([('data', 128)])

        self.comb += If(sink_inject.valid,
            sink_inject.connect(source),
        ).Else(
            sink.connect(source),
        )

class Monitor(Module):
    def __init__(self, stream):
        # Exported signals.
        self.total = Signal(32)
        self.lost = Signal(16)

        # Internal signals (pre CDC).
        total = Signal(32)
        lost = Signal(16)

        self.sync.trace += [
            If(stream.valid,
                total.eq(total + 1),
            ),
            If(stream.valid & ~stream.ready,
                lost.eq(lost + 1),
            ),
        ]

        self.specials += [
            MultiReg(total, self.total),
            MultiReg(lost, self.lost),
        ]

class Keepalive(Module):
    def __init__(self):
        self.source = source = Endpoint([('data', 128)])

        self.lost_frames = Signal(16)
        self.total_frames = Signal(32)
        leds = Signal(8)

        self.comb += source.data.eq(Cat(
            C(0xa6, 8),
            C(0, 32),
            leds,
            self.lost_frames,
            self.total_frames,
            C(0x7fffffff, 32),
        ))

        cnt = Signal(max = 7500000)

        self.sync += [
            If(cnt > 0,
                cnt.eq(cnt - 1),
            ),
            If(source.valid & source.ready,
                cnt.eq(7500000 - 1),
            ),
        ]

        self.comb += [
            source.valid.eq(cnt == 0),
            #source.first.eq(1),
            source.last.eq(1),
        ]

class TraceCore(Module):
    def __init__(self, platform):
        self.clock_domains.cd_trace = ClockDomain()

        pads = platform.request('trace')

        self.source = source = Endpoint([('data', 128)])

        # Main pipeline.
        phy = ClockDomainsRenamer('trace')(TracePHY(pads))

        fifo = ClockDomainsRenamer({'write': 'trace', 'read': 'sys'})(AsyncFIFO([('data', 128)], 512))

        byteswap = ByteSwap(16)

        injector = Injector()

        self.submodules += Pipeline(phy, fifo, byteswap, injector, source)

        self.submodules += phy, fifo, byteswap, injector

        # Monitoring/keepalive.
        monitor = Monitor(phy.source)

        keepalive = Keepalive()

        self.comb += [
            keepalive.total_frames.eq(monitor.total),
            keepalive.lost_frames.eq(monitor.lost),
            keepalive.source.connect(injector.sink_inject),
        ]

        self.submodules += monitor, keepalive

        loss_timeout = Signal(max = 7500000)
        self.loss = Signal()
        last_lost_frames = Signal(16)

        self.sync += [
            last_lost_frames.eq(monitor.lost),
            If(loss_timeout != 0,
                loss_timeout.eq(loss_timeout - 1),
            ),
            If(last_lost_frames != monitor.lost,
                loss_timeout.eq(7500000 - 1),
            ),
        ]

        self.comb += self.loss.eq(loss_timeout != 0)

        # Add verilog sources.
        platform.add_source('verilog/traceIF.v') # TODO: make sure the path is correct
