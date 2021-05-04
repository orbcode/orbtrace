
#
# This file is part of LUNA.
#
# Copyright (c) 2020 Great Scott Gadgets <info@greatscottgadgets.com>
# Edits (c) 2021 Dave Marples <dave@marples.net>
# SPDX-License-Identifier: BSD-3-Clause

""" ecpix5 platform definitions.

This is a non-core platform. It originates from the luna ECPIX-5 platform with extensive edits.

"""

from nmigen import *
from nmigen.build import *
from nmigen.vendor.lattice_ecp5 import LatticeECP5Platform

from nmigen_boards.resources import *
from nmigen_boards.ecpix5 import ECPIX545Platform as _ECPIX545Platform
from nmigen_boards.ecpix5 import ECPIX585Platform as _ECPIX585Platform

from luna.gateware.platform.core  import LUNAPlatform

__all__ = ["ECPIX5_45F_Platform", "ECPIX5_85F_Platform"]


class ECPIX5DomainGenerator(Elaboratable):
    """ Clock generator for ECPIX5 boards. """

    def __init__(self, *, clock_frequencies=None, clock_signal_name=None):
        pass

    def elaborate(self, platform):
        m = Module()

        # Create our domains.
        m.domains.sync   = ClockDomain()
        m.domains.sys2x  = ClockDomain()
        m.domains.usb    = ClockDomain()

        # Grab our clock and global reset signals.
        clk100 = platform.request(platform.default_clk)
        reset  = platform.request(platform.default_rst)

        # Generate the clocks we need
        feedback = Signal()
        locked   = Signal()
        m.submodules.pll = Instance("EHXPLLL",

                # Clock in.
                i_CLKI=clk100,

                # Generated clock outputs.
                o_CLKOP=feedback,
                o_CLKOS= ClockSignal("sync"),
                o_CLKOS2=ClockSignal("sys2x"),

                # Status.
                o_LOCK=locked,

                # PLL parameters...
                p_CLKI_DIV=1,
                p_PLLRST_ENA="DISABLED",
                p_INTFB_WAKE="DISABLED",
                p_STDBY_ENABLE="DISABLED",
                p_DPHASE_SOURCE="DISABLED",
                p_CLKOS3_FPHASE=0,
                p_CLKOS3_CPHASE=0,
                p_CLKOS2_FPHASE=0,
                p_CLKOS2_CPHASE=0,
                p_CLKOS_FPHASE=0,
                p_CLKOS_CPHASE=5,
                p_CLKOP_FPHASE=0,
                p_CLKOP_CPHASE=4,
                p_PLL_LOCK_MODE=0,
                p_CLKOS_TRIM_DELAY="0",
                p_CLKOS_TRIM_POL="FALLING",
                p_CLKOP_TRIM_DELAY="0",
                p_CLKOP_TRIM_POL="FALLING",
                p_OUTDIVIDER_MUXD="DIVD",
                p_CLKOS3_ENABLE="DISABLED",
                p_OUTDIVIDER_MUXC="DIVC",
                p_CLKOS2_ENABLE="ENABLED",
                p_OUTDIVIDER_MUXB="DIVB",
                p_CLKOS_ENABLE="ENABLED",
                p_OUTDIVIDER_MUXA="DIVA",
                p_CLKOP_ENABLE="ENABLED",
                p_CLKOS3_DIV=1,
                p_CLKOS2_DIV=5,
                p_CLKOS_DIV=6,
                p_CLKOP_DIV=6,
                p_CLKFB_DIV=1,
                p_FEEDBK_PATH="CLKOP",

                # Internal feedback.
                i_CLKFB=feedback,

                # Control signals.
                i_RST=reset,
                i_PHASESEL0=0,
                i_PHASESEL1=0,
                i_PHASEDIR=1,
                i_PHASESTEP=1,
                i_PHASELOADREG=1,
                i_STDBY=0,
                i_PLLWAKESYNC=0,

                # Output Enables.
                i_ENCLKOP=0,
                i_ENCLKOS=0,
                i_ENCLKOS2=0,
                i_ENCLKOS3=0,

                # Synthesis attributes.
                a_ICP_CURRENT="12",
                a_LPF_RESISTOR="8"
        )

        # Control our resets.
        m.d.comb += [
            ResetSignal("sync")    .eq(~locked),
            ResetSignal("sys2x")   .eq(~locked),
            ResetSignal("usb")     .eq(~locked),
        ]

        return m


class _ECPIXExtensions:

    # Create a reference

    additional_resources = [

        # trace resources
        Resource("tracein", 0,
                 Subsignal("clk", Pins("E14", dir="i")),
                 Subsignal("dat", Pins("A15 B14 A14 C14", dir="i"), Attrs(IO_TYPE="LVCMOS33"))
        ),

        # swd resources
        Resource("dbgif", 0,
                 Subsignal("tck_swclk",Pins("B17", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
                 Subsignal("nvdriveen", Pins("C18", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
                 Subsignal("swdwr", Pins("B19", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
                 Subsignal("reseten", Pins("A17", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
                 Subsignal("nvsen", Pins("A18", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
                 Subsignal("tdi", Pins("A19", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
                 Subsignal("tms_swdio",Pins("C19", dir="io"), Attrs(IO_TYPE="LVCMOS33")),

                 Subsignal("tdo_swo", Pins("B16", dir="i"), Attrs(IO_TYPE="LVCMOS33")),
                 Subsignal("nreset_sense", Pins("A16", dir="i"), Attrs(IO_TYPE="LVCMOS33")),
        ),

        # debug serial resources
        Resource("dbguart",
                 Subsignal("txd", Pins("C16", dir="o")),
                 Subsignal("rxd", Pins("D14", dir="i"))
        ),

        Resource("canary", 0, Pins("E26", dir="o"), Attrs(IO_TYPE="LVCMOS33"))
    ]



class ECPIX5_45F_Platform(_ECPIX545Platform, _ECPIXExtensions, LUNAPlatform):
    name                   = "ECPIX-5 (45F)"

    clock_domain_generator = ECPIX5DomainGenerator
    default_usb_connection = "ulpi"

    # Create our semantic aliases.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_resources(self.additional_resources)



class orbtrace_ECPIX5_85_Platform(_ECPIX585Platform, _ECPIXExtensions, LUNAPlatform):
    name                   = "ECPIX-5 (85F)"

    clock_domain_generator = ECPIX5DomainGenerator
    default_usb_connection = "ulpi"

    # Create our semantic aliases.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_resources(self.additional_resources)
