from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.stream import Endpoint, AsyncFIFO, Pipeline, CombinatorialActor, Converter, SyncFIFO, PipeValid
from litex.build.io import DDRInput

from .swo import ManchesterDecoder, PulseLengthCapture, BitsToBytes, NRZDecoder, UARTDecoder

from . import cobs, tpiu

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

        self.width = Signal(2)

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
            i_width = self.width,
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
    def __init__(self, stream, cd):
        # Exported signals.
        self.total = Signal(32)
        self.lost = Signal(16)
        self.clk = Signal(2)

        # Internal signals (pre CDC).
        total = Signal(32)
        lost = Signal(16)
        clk = Signal(2)

        _sync = getattr(self.sync, cd)
        _sync += [
            If(stream.valid,
                total.eq(total + 1),
            ),
            If(stream.valid & ~stream.ready,
                lost.eq(lost + 1),
            ),
            clk.eq(clk + 1),
        ]

        self.specials += [
            MultiReg(total, self.total),
            MultiReg(lost, self.lost),
            MultiReg(clk, self.clk),
        ]

class Indicator(Module):
    def __init__(self, data, hold):
        self.out = Signal()

        last_data = Signal(len(data))
        hold_cnt = Signal(max = hold)

        self.sync += [
            last_data.eq(data),
            If(hold_cnt != 0,
                hold_cnt.eq(hold_cnt - 1),
            ),
            If(last_data != data,
                hold_cnt.eq(hold - 1),
            ),
        ]

        self.comb += self.out.eq(hold_cnt != 0)

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

class StreamFlush(Module):
    def __init__(self, timeout):
        self.sink = sink = Endpoint([('data', 8)])
        self.source = source = Endpoint([('data', 8)])

        timeout_cnt = Signal(max = timeout + 1)
        timeout_hit = Signal()

        data = Signal(8)
        first = Signal()
        last = Signal()
        valid = Signal()

        self.comb += [
            timeout_hit.eq(timeout_cnt == 0),

            sink.ready.eq(~valid | (source.ready & source.valid)),

            source.data.eq(data),
            source.first.eq(first),
            source.last.eq(last | timeout_hit),
            source.valid.eq(valid & (sink.valid | timeout_hit)),
        ]

        self.sync += [
            If(valid & ~timeout_hit,
                timeout_cnt.eq(timeout_cnt - 1),
            ),

            If(source.valid & source.ready,
                valid.eq(0),
            ),

            If(sink.valid & sink.ready,
                data.eq(sink.data),
                first.eq(sink.first),
                last.eq(sink.last),
                valid.eq(1),

                If(~valid | timeout_hit,
                    timeout_cnt.eq(timeout),
                ),
            ),
        ]

class Divider(Module):
    def __init__(self, num, den_bits, res_bits):
        self.den = Signal(den_bits)
        self.res = Signal(res_bits)
        self.start = Signal()
        self.done = Signal()
        acc = Signal(max = num + 1)

        self.sync += [
            If(self.start,
                acc.eq(num),
                self.res.eq(0),
                self.done.eq(0),
            ),
            If(~self.done,
                If((acc >= self.den) & (self.res != (2**res_bits - 1)),
                    acc.eq(acc - self.den),
                    self.res.eq(self.res + 1),
                ).Else(
                    self.done.eq(1),
                ),
            ),
        ]

class TraceCore(Module):
    def __init__(self, platform):
        self.source = source = Endpoint([('data', 8)])

        # Input format.
        self.input_format = Signal(8)

        trace_active = Signal()
        trace_width = Signal(2)
        swo_active = Signal()
        swo_manchester = Signal()
        swo_nrz = Signal()
        swo_tpiu = Signal()
        swo_itm = Signal()

        self.comb += Case(self.input_format, {
            0x01: [
                trace_active.eq(1),
                trace_width.eq(1),
            ],
            0x02: [
                trace_active.eq(1),
                trace_width.eq(2),
            ],
            0x03: [
                trace_active.eq(1),
                trace_width.eq(3),
            ],
            0x10: [
                swo_active.eq(1),
                swo_manchester.eq(1),
                swo_itm.eq(1),
            ],
            0x11: [
                swo_active.eq(1),
                swo_manchester.eq(1),
                swo_tpiu.eq(1),
            ],
            0x12: [
                swo_active.eq(1),
                swo_nrz.eq(1),
                swo_itm.eq(1),
            ],
            0x13: [
                swo_active.eq(1),
                swo_nrz.eq(1),
                swo_tpiu.eq(1),
            ],
        })

        # Async baudrate.
        self.async_baudrate = Signal(32)
        self.async_baudrate_strobe = Signal()
        self.async_bitlen = Signal(16, reset = 8000)

        self.submodules.baudrate_divider = Divider(8000000000, 32, 16)
        self.comb += [
            self.baudrate_divider.den.eq(self.async_baudrate),
            self.baudrate_divider.start.eq(self.async_baudrate_strobe),
            self.async_bitlen.eq(self.baudrate_divider.res),
        ]

        # Trace pipeline.
        self.clock_domains.cd_trace = ClockDomain()
        trace_pads = platform.request('trace')

        trace_pipeline = [
            phy := ClockDomainsRenamer('trace')(TracePHY(trace_pads)),
            ClockDomainsRenamer({'write': 'trace', 'read': 'sys'})(AsyncFIFO([('data', 128)], 4)),
        ]

        #pv.comb += pv.source.last.eq(1)

        trace_stream = Endpoint([('data', 128)])

        self.submodules += [*trace_pipeline, Pipeline(*trace_pipeline, trace_stream)]

        # Trace config.
        self.comb += phy.width.eq(trace_width)

        # Trace monitoring/keepalive.
        monitor = Monitor(phy.source, 'trace')

        keepalive = Keepalive()

        self.comb += [
            keepalive.total_frames.eq(monitor.total),
            keepalive.lost_frames.eq(monitor.lost),
            #keepalive.source.connect(injector.sink_inject),
        ]

        self.submodules += monitor, keepalive

        # SWO pipeline.
        self.swo = Signal(2)

        swo_stream_frontend_source = Endpoint([('count', 16), ('level', 1)])
        swo_pipeline_frontend = [
            swo_phy := ClockDomainsRenamer('swo2x')(PulseLengthCapture(16)),
            ClockDomainsRenamer({'write': 'swo2x', 'read': 'swo'})(AsyncFIFO([('count', 16), ('level', 1)], 8)),
        ]
        self.submodules += [*swo_pipeline_frontend, Pipeline(*swo_pipeline_frontend, swo_stream_frontend_source)]

        swo_stream_manchester_sink = Endpoint([('count', 16), ('level', 1)])
        swo_stream_manchester_source = Endpoint([('data', 8)])
        swo_pipeline_manchester = [
            ClockDomainsRenamer('swo')(ManchesterDecoder(16)),
            ClockDomainsRenamer('swo')(BitsToBytes()),
        ]
        self.submodules += [*swo_pipeline_manchester, Pipeline(swo_stream_manchester_sink, *swo_pipeline_manchester, swo_stream_manchester_source)]

        swo_stream_nrz_sink = Endpoint([('count', 16), ('level', 1)])
        swo_stream_nrz_source = Endpoint([('data', 8)])
        swo_pipeline_nrz = [
            nrz_decoder := ClockDomainsRenamer('swo')(NRZDecoder(16)),
            ClockDomainsRenamer('swo')(UARTDecoder()),
        ]
        self.submodules += [*swo_pipeline_nrz, Pipeline(swo_stream_nrz_sink, *swo_pipeline_nrz, swo_stream_nrz_source)]

        swo_stream_backend_sink = Endpoint([('data', 8)])
        swo_stream_backend_source = Endpoint([('data', 8)])
        swo_pipeline_backend = [
            ClockDomainsRenamer({'write': 'swo', 'read': 'sys'})(AsyncFIFO([('data', 8)], 4)),
            #StreamFlush(7500000),
        ]
        self.submodules += [*swo_pipeline_backend, Pipeline(swo_stream_backend_sink, *swo_pipeline_backend, swo_stream_backend_source)]

        self.comb += swo_phy.input_signal.eq(self.swo)
        self.comb += nrz_decoder.bitlen.eq(self.async_bitlen)

        # SWO monitoring.
        swo_monitor = Monitor(swo_stream_backend_source, 'swo')
        self.submodules += swo_monitor

        # Indicators
        self.led_overrun = Signal()
        self.led_data = Signal()
        self.led_clk = Signal()

        self.submodules.overrun_indicator = Indicator(monitor.lost, 7500000)
        self.submodules.data_indicator = Indicator(monitor.total, 7500000)
        self.submodules.clk_indicator = Indicator(monitor.clk, 7500000)

        self.submodules.swo_overrun_indicator = Indicator(swo_monitor.lost, 7500000)
        self.submodules.swo_data_indicator = Indicator(swo_monitor.total, 7500000)

        # Orbflow pipeline
        orbflow_pipeline_sink = Endpoint([('data', 128)])
        orbflow_pipeline = [
            ByteSwap(16),
            tpiu_demux := tpiu.TPIUDemux(),
            cobs.ChecksumAppender(),
            cobs.COBSEncoder(),
            cobs.DelimiterAppender(),
            cobs.SuperFramer(7500000, 65536),
            SyncFIFO([('data', 8)], 8192, buffered = True),
        ]
        self.submodules += [*orbflow_pipeline, Pipeline(orbflow_pipeline_sink, *orbflow_pipeline, source)]

        self.submodules.swo_tpiu_sync = swo_tpiu_sync = tpiu.TPIUSync()

        # Output mux
        self.comb += [
            If(trace_active,
                trace_stream.connect(orbflow_pipeline_sink),
                self.led_overrun.eq(self.overrun_indicator.out),
                self.led_data.eq(self.data_indicator.out),
                self.led_clk.eq(self.clk_indicator.out),
            ),
            If(swo_active,
                self.led_overrun.eq(self.swo_overrun_indicator.out),
                self.led_data.eq(self.swo_data_indicator.out),
            ),
            If(swo_manchester,
                swo_stream_frontend_source.connect(swo_stream_manchester_sink),
                swo_stream_manchester_source.connect(swo_stream_backend_sink),
            ),
            If(swo_nrz,
                swo_stream_frontend_source.connect(swo_stream_nrz_sink),
                swo_stream_nrz_source.connect(swo_stream_backend_sink),
            ),
            If(swo_tpiu,
                swo_stream_backend_source.connect(swo_tpiu_sync.sink),
                swo_tpiu_sync.source.connect(orbflow_pipeline_sink),
            ),
            If(swo_itm,
                swo_stream_backend_source.connect(tpiu_demux.bypass_sink),
                tpiu_demux.bypass.eq(1),
            ),
        ]

        # Add verilog sources.
        platform.add_source('verilog/traceIF.v') # TODO: make sure the path is correct
