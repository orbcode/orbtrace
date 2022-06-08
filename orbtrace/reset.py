from migen import *

from litex.soc.interconnect.csr import AutoCSR, CSRStorage

class Reset(Module, AutoCSR):
    def __init__(self):
        self._ctl = CSRStorage(1)

        self.reset = Signal()

        self.comb += self.reset.eq(self._ctl.storage)
