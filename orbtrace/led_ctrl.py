from migen import *

from litex.soc.interconnect.csr import AutoCSR, CSRStorage

class LEDCtrl(Module, AutoCSR):
    def __init__(self, num, reset_value):
        self._set = CSRStorage(num * 4, reset_value)

        self.inputs = leds = Array(Record([('r', 1), ('g', 1), ('b', 1)]) for i in range(num))
        self.outputs = leds = Array(Record([('r', 1), ('g', 1), ('b', 1)]) for i in range(num))

        for i in range(num):
            self.comb += If(self._set.storage[i*4 + 3],
                self.outputs[i].r.eq(self._set.storage[i*4 + 0]),
                self.outputs[i].g.eq(self._set.storage[i*4 + 1]),
                self.outputs[i].b.eq(self._set.storage[i*4 + 2]),
            ).Else(
                self.outputs[i].eq(self.inputs[i])
            )
