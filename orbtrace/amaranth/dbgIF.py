#SPDX-License-Identifier: BSD-3-Clause

from amaranth                  import *
from amaranth.hdl.xfrm         import DomainRenamer
from amaranth.lib.fifo         import SyncFIFOBuffered

# Glue to connect amaranth world (cmsis_dap) to verilog world
# ===========================================================

class DBGIF(Elaboratable):
    def __init__(self, dbgpins):
        self.dbgpins      = dbgpins;
        self.turnaround   = Signal(4, reset=1);
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

    def elaborate(self, platform):
        m = Module()
        swin = Signal();
        swout = Signal();

        m.submodules.dbgif = Instance(
            "dbgIF",
            i_rst = ResetSignal("debug"),
            i_clk = ClockSignal("debug"),

            # Downwards interface to the pins
            i_swdi            = self.dbgpins.tms_swdio.i,
            o_tms_swdo        = self.dbgpins.tms_swdio.o,
            o_swwr            = self.dbgpins.swdwr.o,
            o_tck_swclk       = self.dbgpins.tck_swclk.o,
            o_tdi             = self.dbgpins.tdi.o,
            i_tdo_swo         = self.dbgpins.tdo_swo.i,

            i_tgt_reset_state = self.dbgpins.nreset_sense,
            o_tgt_reset_pin   = self.dbgpins.reseten,

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
            i_dev     = self.dev
            )

        i_clk = ClockSignal("debug")
        m.d.comb += [
            self.dbgpins.tms_swdio.oe.eq(self.dbgpins.swdwr.o),

            self.dbgpins.tms_swdio.o_clk.eq(i_clk),
            self.dbgpins.tms_swdio.i_clk.eq(i_clk),
            self.dbgpins.swdwr.o_clk.eq(i_clk),

            self.dbgpins.tdi.o_clk.eq(i_clk),
            self.dbgpins.tdo_swo.i_clk.eq(i_clk),
        ]
        return m
