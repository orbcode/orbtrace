from migen import *

from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus

class TestIO(Module, AutoCSR):
    def __init__(self, signals):
        self._oe = CSRStorage(len(signals))
        self._in = CSRStatus(len(signals))
        self._out = CSRStorage(len(signals))

        for i, signal in enumerate(signals):
            if len(signal) == 1:
                self.comb += self._in.status[i].eq(signal[0])

            else:
                io, dir = signal
                t = TSTriple()
                self.specials += t.get_tristate(io)
                self.comb += [
                    self._in.status[i].eq(t.i),
                    t.o.eq(self._out.storage[i]),
                    t.oe.eq(self._oe.storage[i]),
                    dir.eq(self._oe.storage[i]),
                ]
