from amaranth import *
from amaranth.lib import wiring, stream

from ..stream import Packet, SyncFIFOBuffered, AsyncFIFOBuffered

from . import swo, tpiu, cobs, orbflow, util

class TraceIF(wiring.Component):
    output: wiring.Out(stream.Signature(tpiu.TPIURawFrame))

    width: wiring.In(2)

    trace_a: wiring.In(4)
    trace_b: wiring.In(4)

    def elaborate(self, platform):
        m = Module()

        frame = Signal(128)
        fravail = Signal()
        fravail_last = Signal()

        for byte, bit in zip(range(16), reversed(range(0, 128, 8))):
            m.d.comb += self.output.payload[byte].eq(frame[bit:bit + 8])

        m.d.sync += fravail_last.eq(fravail)
        m.d.comb += self.output.valid.eq(fravail != fravail_last)

        m.submodules.traceif = Instance('traceIF',
            i_traceClkin = ClockSignal(),
            i_rst = ResetSignal(),
            i_traceDina = self.trace_a,
            i_traceDinb = self.trace_b,
            i_width = self.width,

            o_Frame = frame,
            o_FrAvail = fravail,
            #o_edgeOutput = edgeOutput,
        )

        return m

class TraceCore(wiring.Component):
    output: wiring.Out(stream.Signature(Packet(has_last = True)))

    output_compat_data: wiring.Out(8)
    output_compat_last: wiring.Out(1)

    input_format: wiring.In(8)
    input_format_strobe: wiring.In(1)

    async_baudrate: wiring.In(32)
    async_baudrate_strobe: wiring.In(1)

    trace_a: wiring.In(4)
    trace_b: wiring.In(4)

    swo: wiring.In(2)

    led_overrun: wiring.Out(1)
    led_data: wiring.Out(1)
    led_clk: wiring.Out(1)

    def elaborate(self, platform):
        m = Module()

        m.submodules.pulse_length_capture = pulse_length_capture = DomainRenamer('swo2x')(swo.PulseLengthCapture())
        m.submodules.swo2x_fifo = swo2x_fifo = DomainRenamer({'write': 'swo2x', 'read': 'swo'})(AsyncFIFOBuffered(swo.PulseLength, 8))

        m.submodules.manchester_decoder = manchester_decoder = DomainRenamer('swo')(swo.ManchesterDecoder())
        m.submodules.bits_to_bytes = bits_to_bytes = DomainRenamer('swo')(swo.BitsToBytes())

        m.submodules.nrz_decoder = nrz_decoder = DomainRenamer('swo')(swo.NRZDecoder())
        m.submodules.uart_decoder = uart_decoder = DomainRenamer('swo')(swo.UARTDecoder())

        m.submodules.swo_fifo = swo_fifo = DomainRenamer({'write': 'swo', 'read': 'sync'})(AsyncFIFOBuffered(8, 16))

        m.submodules.traceif = traceif = DomainRenamer('trace')(TraceIF())
        m.submodules.trace_fifo = trace_fifo = DomainRenamer({'write': 'trace', 'read': 'sync'})(AsyncFIFOBuffered(tpiu.TPIURawFrame, 4))

        m.submodules.tpiu_sync = tpiu_sync = tpiu.TPIUSync()
        m.submodules.tpiu_demux = tpiu_demux = tpiu.TPIUDemux()
        m.submodules.checksum_appender = checksum_appender = orbflow.ChecksumAppender()
        m.submodules.cobs_encoder = cobs_encoder = cobs.COBSEncoder(append_delimiter = True)
        m.submodules.superframer = superframer = orbflow.SuperFramer(7_500_000, 65536)
        m.submodules.fifo = fifo = SyncFIFOBuffered(Packet(has_last = True), 8192)

        m.submodules.baudrate_divider = baudrate_divider = util.Divider(8_000_000_000, 32, 16)

        m.d.comb += [
            baudrate_divider.den.eq(self.async_baudrate),
            baudrate_divider.start.eq(self.async_baudrate_strobe),
            nrz_decoder.bitlen.eq(baudrate_divider.res),
        ]

        m.d.comb += pulse_length_capture.input.eq(self.swo)
        wiring.connect(m, pulse_length_capture.output, swo2x_fifo.input)
        wiring.connect(m, manchester_decoder.output, bits_to_bytes.input)
        wiring.connect(m, nrz_decoder.output, uart_decoder.input)

        with m.Switch(self.input_format):
            with m.Case(0x10, 0x11):
                wiring.connect(m, swo2x_fifo.output, manchester_decoder.input)
                wiring.connect(m, bits_to_bytes.output, swo_fifo.input)

            with m.Case(0x12, 0x13):
                wiring.connect(m, swo2x_fifo.output, nrz_decoder.input)
                wiring.connect(m, uart_decoder.output, swo_fifo.input)

        m.d.comb += traceif.trace_a.eq(self.trace_a)
        m.d.comb += traceif.trace_b.eq(self.trace_b)
        wiring.connect(m, traceif.output, trace_fifo.input)

        with m.Switch(self.input_format):
            with m.Case(0x01, 0x02, 0x03):
                wiring.connect(m, trace_fifo.output, tpiu_demux.input)
                m.d.comb += traceif.width.eq(self.input_format)

            with m.Case(0x11, 0x13):
                wiring.connect(m, swo_fifo.output, tpiu_sync.input)
                wiring.connect(m, tpiu_sync.output, tpiu_demux.input)

            with m.Case(0x10, 0x12):
                wiring.connect(m, swo_fifo.output, tpiu_demux.input_bypass)
                m.d.comb += tpiu_demux.bypass.eq(1)

        wiring.connect(m, tpiu_demux.output, checksum_appender.input)
        wiring.connect(m, checksum_appender.output, cobs_encoder.input)
        wiring.connect(m, cobs_encoder.output, superframer.input)
        wiring.connect(m, superframer.output, fifo.input)
        wiring.connect(m, fifo.output, wiring.flipped(self.output))

        m.d.comb += tpiu_sync.reset_sync.eq(self.input_format_strobe)

        m.d.comb += [
            self.output_compat_data.eq(self.output.payload.data),
            self.output_compat_last.eq(self.output.payload.last),
        ]

        m.submodules.trace_monitor = trace_monitor = util.Monitor(trace_fifo.input, 'trace')
        m.submodules.swo_monitor = swo_monitor = util.Monitor(swo_fifo.input, 'swo')

        m.submodules.trace_overrun_indicator = trace_overrun_indicator = util.Indicator(trace_monitor.lost, 7_500_000)
        m.submodules.trace_data_indicator = trace_data_indicator = util.Indicator(trace_monitor.total, 7_500_000)
        m.submodules.trace_clk_indicator = trace_clk_indicator = util.Indicator(trace_monitor.clk, 7_500_000)

        m.submodules.swo_overrun_indicator = swo_overrun_indicator = util.Indicator(swo_monitor.lost, 7_500_000)
        m.submodules.swo_data_indicator = swo_data_indicator = util.Indicator(swo_monitor.total, 7_500_000)

        with m.Switch(self.input_format):
            with m.Case(0x01, 0x02, 0x03):
                m.d.comb += [
                    self.led_overrun.eq(trace_overrun_indicator.output),
                    self.led_data.eq(trace_data_indicator.output),
                    self.led_clk.eq(trace_clk_indicator.output),
                ]

            with m.Case(0x10, 0x11, 0x12, 0x13):
                m.d.comb += [
                    self.led_overrun.eq(swo_overrun_indicator.output),
                    self.led_data.eq(swo_data_indicator.output),
                ]

        return m
