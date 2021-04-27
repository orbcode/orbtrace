from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.soc.cores.clock import ECP5PLL

class CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.clock_domains.cd_init    = ClockDomain()
        self.clock_domains.cd_por     = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys     = ClockDomain()
        self.clock_domains.cd_sys2x   = ClockDomain()
        self.clock_domains.cd_sys2x_i = ClockDomain(reset_less=True)

        # # #

        self.stop  = Signal()
        self.reset = Signal()

        # Clk / Rst
        clk_in = platform.request(platform.default_clk_name)
        clk_in_freq = round(1e9 / platform.default_clk_period)

        #rst_n  = platform.request("rst_n")

        # Power on reset
        por_count = Signal(16, reset=2**16-1)
        por_done  = Signal()
        self.comb += self.cd_por.clk.eq(clk_in)
        self.comb += por_done.eq(por_count == 0)
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))

        # PLL
        self.submodules.pll = pll = ECP5PLL()
        #self.comb += pll.reset.eq(~por_done | ~rst_n | self.rst)
        self.comb += pll.reset.eq(~por_done | self.rst)
        pll.register_clkin(clk_in, clk_in_freq)
        #pll.create_clkout(self.cd_sys2x_i, 2*sys_clk_freq)
        pll.create_clkout(self.cd_sys2x, 2*sys_clk_freq)
        pll.create_clkout(self.cd_init, 25e6)
        self.specials += [
            #Instance("ECLKSYNCB",
            #    i_ECLKI = self.cd_sys2x_i.clk,
            #    i_STOP  = self.stop,
            #    o_ECLKO = self.cd_sys2x.clk),
            Instance("CLKDIVF",
                p_DIV     = "2.0",
                i_ALIGNWD = 0,
                i_CLKI    = self.cd_sys2x.clk,
                i_RST     = self.reset,
                o_CDIVX   = self.cd_sys.clk),
            AsyncResetSynchronizer(self.cd_sys,   ~pll.locked | self.reset | self.rst),
            #AsyncResetSynchronizer(self.cd_sys2x, ~pll.locked | self.reset | self.rst),
        ]

    def add_usb(self):
        self.clock_domains.cd_usb = ClockDomain()
        self.pll.create_clkout(self.cd_usb, 60e6)
