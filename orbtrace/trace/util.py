from amaranth import *
from amaranth.lib import wiring, cdc

class Monitor(wiring.Component):
    total: wiring.Out(2)
    lost: wiring.Out(2)
    clk: wiring.Out(2)

    def __init__(self, stream, cd):
        super().__init__()
        self._stream = stream
        self._cd = cd

    def elaborate(self, platform):
        m = Module()

        total = Signal(2)
        lost = Signal(2)
        clk = Signal(2)

        with m.If(self._stream.valid):
            m.d[self._cd] += total.eq(total + 1)

        with m.If(self._stream.valid & ~self._stream.ready):
            m.d[self._cd] += lost.eq(lost + 1)

        m.d[self._cd] += clk.eq(clk + 1)

        m.submodules += [
            cdc.FFSynchronizer(total, self.total),
            cdc.FFSynchronizer(lost, self.lost),
            cdc.FFSynchronizer(clk, self.clk),
        ]

        return m

class Indicator(wiring.Component):
    output: wiring.Out(1)

    def __init__(self, signal, hold):
        super().__init__()
        self._signal = signal
        self._hold = hold

    def elaborate(self, platform):
        m = Module()

        last_signal = Signal.like(self._signal)
        hold_cnt = Signal(range(self._hold))

        m.d.sync += last_signal.eq(self._signal)

        with m.If(hold_cnt != 0):
            m.d.sync += hold_cnt.eq(hold_cnt - 1)

        with m.If(last_signal != self._signal):
            m.d.sync += hold_cnt.eq(self._hold - 1)

        m.d.comb += self.output.eq(hold_cnt != 0)

        return m

class Divider(wiring.Component):
    def __init__(self, num, den_bits, res_bits):
        super().__init__({
            'den': wiring.Out(den_bits),
            'res': wiring.Out(res_bits),
            'start': wiring.In(1),
            'done': wiring.Out(1),
        })
        self.num = num
        self.den_bits = den_bits
        self.res_bits = res_bits

    def elaborate(self, platform):
        m = Module()

        acc = Signal(range(self.num + 1))

        with m.If(self.start):
            m.d.sync += [
                acc.eq(self.num),
                self.res.eq(0),
                self.done.eq(0),
            ]

        with m.If(~self.done):
            with m.If((acc >= self.den) & (self.res != (2**self.res_bits - 1))):
                m.d.sync += [
                    acc.eq(acc - self.den),
                    self.res.eq(self.res + 1),
                ]
            with m.Else():
                m.d.sync += self.done.eq(1)

        return m
