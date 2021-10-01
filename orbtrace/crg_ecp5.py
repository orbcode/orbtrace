from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.soc.cores.clock import ECP5PLL

from litex.soc.interconnect.csr import AutoCSR, CSRStorage

class CRG(Module, AutoCSR):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.clock_domains.cd_por      = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys      = ClockDomain()
        self.clock_domains.cd_sys2x    = ClockDomain()
        self.clock_domains.cd_sys_90   = ClockDomain()
        self.clock_domains.cd_sys2x_90 = ClockDomain()
        #self.clock_domains.cd_sys2x_i = ClockDomain(reset_less=True)

        # # #

        self.stop  = Signal()
        self.reset = Signal()

        # Clk / Rst
        clk_in = platform.request(platform.default_clk_name)
        clk_in_freq = round(1e9 / platform.default_clk_period)

        # Power on reset
        por_count = Signal(16, reset=2**16-1)
        por_done  = Signal()
        self.comb += self.cd_por.clk.eq(clk_in)
        self.comb += por_done.eq(por_count == 0)
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))

        # PLL
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~por_done | self.rst)
        pll.register_clkin(clk_in, clk_in_freq)
        pll.create_clkout(self.cd_sys2x, 2*sys_clk_freq, margin = 0)
        pll.create_clkout(self.cd_sys2x_90, 2*sys_clk_freq, margin = 0, phase = 1)

        self._slip_hr2x = CSRStorage()
        self._slip_hr2x90 = CSRStorage()

        self.specials += [
            #Instance("ECLKSYNCB",
            #    i_ECLKI = self.cd_sys2x_i.clk,
            #    i_STOP  = self.stop,
            #    o_ECLKO = self.cd_sys2x.clk),
            Instance("CLKDIVF",
                p_DIV     = "2.0",
                i_ALIGNWD = self._slip_hr2x.storage,
                i_CLKI    = self.cd_sys2x.clk,
                i_RST     = ~pll.locked,
                o_CDIVX   = self.cd_sys.clk),
            AsyncResetSynchronizer(self.cd_sys,   ~pll.locked | self.reset | self.rst),

            Instance("CLKDIVF",
                p_DIV     = "2.0",
                i_ALIGNWD = self._slip_hr2x90.storage,
                i_CLKI    = self.cd_sys2x_90.clk,
                i_RST     = ~pll.locked,
                o_CDIVX   = self.cd_sys_90.clk),
            AsyncResetSynchronizer(self.cd_sys_90,   ~pll.locked | self.reset | self.rst),
        
        ]
        #self.comb += self.cd_sys.clk.eq(self.cd_hr.clk)

        pll.expose_dpa()

        self._phase_sel = CSRStorage(2)
        self._phase_dir = CSRStorage()
        self._phase_step = CSRStorage()
        self._phase_load = CSRStorage()

        self.comb += [
            self.pll.phase_sel.eq(self._phase_sel.storage),
            self.pll.phase_dir.eq(self._phase_dir.storage),
            self.pll.phase_step.eq(self._phase_step.storage),
            self.pll.phase_load.eq(self._phase_load.storage),
        ]

        # PLL2
        self.submodules.pll2 = pll2 = ECP5PLL()
        self.comb += pll2.reset.eq(~por_done | self.rst)
        pll2.register_clkin(clk_in, clk_in_freq)

    def add_usb(self):
        self.clock_domains.cd_usb = ClockDomain()
        self.pll.create_clkout(self.cd_usb, 60e6)

    def add_debug(self):
        self.clock_domains.cd_debug = ClockDomain()
        self.pll2.create_clkout(self.cd_debug, 120e6)
