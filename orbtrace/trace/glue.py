from migen import *

from litex.soc.interconnect.stream import Endpoint
from litex.build.io import DDRInput

from . import core

class TraceIO(Module):
    def __init__(self, pads):
        traceclk = Signal()
        tracedata = Signal(4)

        self.comb += [
            traceclk.eq(pads.clk),
            tracedata.eq(pads.data),
        ]

        self.trace_a = Signal(4)
        self.trace_b = Signal(4)

        for i in range(4):
            self.specials += DDRInput(
                clk = traceclk,
                i = tracedata[i],
                o1 = self.trace_a[i],
                o2 = self.trace_b[i],
            )

        self.comb += ClockSignal().eq(traceclk)

class TraceCore(Module):
    def __init__(self, platform, wrapper):
        self.source = source = Endpoint([('data', 8)])

        self.input_format = Signal(8)
        self.input_format_strobe = Signal()

        self.async_baudrate = Signal(32)
        self.async_baudrate_strobe = Signal()

        self.led_overrun = Signal()
        self.led_data = Signal()
        self.led_clk = Signal()

        self.swo = Signal(2)


        self.clock_domains.cd_trace = ClockDomain()
        trace_pads = platform.request('trace')
        self.submodules.trace_io = trace_io = ClockDomainsRenamer('trace')(TraceIO(trace_pads))


        core_am = core.TraceCore()
        wrapper.m.submodules += core_am

        wrapper.connect_domain('trace')
        wrapper.connect_domain('swo2x')
        wrapper.connect_domain('swo')

        wrapper.connect(trace_io.trace_a, core_am.trace_a)
        wrapper.connect(trace_io.trace_b, core_am.trace_b)
        wrapper.connect(self.swo, core_am.swo)

        wrapper.connect(self.input_format, core_am.input_format)
        wrapper.connect(self.input_format_strobe, core_am.input_format_strobe)

        wrapper.connect(self.async_baudrate, core_am.async_baudrate)
        wrapper.connect(self.async_baudrate_strobe, core_am.async_baudrate_strobe)

        wrapper.connect(source.valid, core_am.output.valid),
        wrapper.connect(source.ready, core_am.output.ready),
        wrapper.connect(source.data, core_am.output_compat_data),
        wrapper.connect(source.last, core_am.output_compat_last),

        wrapper.connect(self.led_overrun, core_am.led_overrun)
        wrapper.connect(self.led_data, core_am.led_data)
        wrapper.connect(self.led_clk, core_am.led_clk)

        platform.add_source('verilog/traceIF.v')
