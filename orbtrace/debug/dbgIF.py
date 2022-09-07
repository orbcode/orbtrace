from migen import *

from litex.build.io import SDRInput, DDRInput, SDROutput, SDRTristate

class DBGIF(Module):
    def __init__(self, pads):
        self.addr32       = Signal(2);
        self.rnw          = Signal();
        self.apndp        = Signal();
        self.dwrite       = Signal(32);
        self.dread        = Signal(32);
        self.perr         = Signal();
        self.go           = Signal();
        self.done         = Signal();
        self.ack          = Signal(3);
        self.pinsin       = Signal(16);
        self.pinsout      = Signal(8);
        self.command      = Signal(5);
        self.dev          = Signal(3);
        self.is_jtag      = Signal()

        tms_swdio_i = Signal()
        tms_swdio_o = Signal()
        tms_swdio_oe = Signal()
        tdi = Signal()

        nreset_sense = Signal()
        reseten = Signal()

        self.specials += SDROutput(
            o = pads.jtms_dir,
            i = tms_swdio_oe,
            clk = ClockSignal('debug'),
        )

        t = TSTriple()
        self.specials += t.get_tristate(pads.jtms)

        self.comb += [
            t.oe.eq(tms_swdio_oe),
            t.o.eq(tms_swdio_o),
            tms_swdio_i.eq(t.i),
        ]

        self.specials += SDROutput(
            o = pads.jtdi,
            i = tdi,
            clk = ClockSignal('debug'),
        )

        jtdo_swo_clk = Signal()

        self.specials += Instance('DCSC',
            o_DCSOUT = jtdo_swo_clk,
            i_CLK0 = ClockSignal('debug'),
            i_CLK1 = ClockSignal('swo2x'),
            i_SEL0 = self.is_jtag,
            i_SEL1 = ~self.is_jtag,
            i_MODESEL = 0,
        )

        self.swo = Signal(2)

        self.specials += DDRInput(
            i = pads.jtdo,
            o1 = self.swo[0],
            o2 = self.swo[1],
            clk = jtdo_swo_clk,
        )

        if hasattr(pads, 'nrst'):
            nrst = TSTriple()
            self.specials += nrst.get_tristate(pads.nrst)

            self.comb += [
                nrst.o.eq(0),
                nrst.oe.eq(reseten),
                nreset_sense.eq(nrst.i),
            ]

            if hasattr(pads, 'nrst_dir'):
                self.comb += pads.nrst_dir.eq(nrst.oe)

        else:
            self.comb += [
                pads.nrst_o_n.eq(reseten),
                nreset_sense.eq(pads.nrst_i),
            ]

        if hasattr(pads, 'jtck_dir'):
            self.comb += pads.jtck_dir.eq(1)

        if hasattr(pads, 'jtdi_dir'):
            self.comb += pads.jtdi_dir.eq(1)

        self.specials += Instance(
            "dbgIF",
            i_rst = ResetSignal("debug"),
            i_clk = ClockSignal("debug"),

            # Downwards interface to the pins
            i_swdi            = tms_swdio_i,
            o_tms_swdo        = tms_swdio_o,
            o_swwr            = tms_swdio_oe,
            o_tck_swclk       = pads.jtck,
            o_tdi             = tdi,
            i_tdo_swo         = self.swo[0],

            i_tgt_reset_state = nreset_sense,
            o_tgt_reset_pin   = reseten,

            # Upwards interface to command controller
            i_addr32     = self.addr32,
            i_rnw        = self.rnw,
            i_apndp      = self.apndp,
            o_ack        = self.ack,
            i_dwrite     = self.dwrite,
            o_dread      = self.dread,
            i_pinsin     = self.pinsin,
            o_pinsout    = self.pinsout,

            i_command = self.command,
            i_go      = self.go,
            o_done    = self.done,
            o_perr    = self.perr,
            i_dev     = self.dev,
        )
