from migen import *

from litex.soc.interconnect.csr import AutoCSR, CSRStorage

class Glitch(Module, AutoCSR):
    def __init__(self, trigger, output):
        self._delay = CSRStorage(32)
        self._pulse = CSRStorage(32)

        cnt = Signal(32)

        self.submodules.fsm = fsm = FSM()

        fsm.act('IDLE',
            If(trigger,
                NextState('DELAY'),
                NextValue(cnt, self._delay.storage),
            )
        )

        fsm.act('DELAY',
            If(cnt,
                NextValue(cnt, cnt - 1),
            ).Else(
                NextState('PULSE'),
                NextValue(cnt, self._pulse.storage),
            )
        )

        fsm.act('PULSE',
            output.eq(1),
            If(cnt,
                NextValue(cnt, cnt - 1),
            ).Else(
                NextState('DONE'),
            )
        )

        fsm.act('DONE',
            If(~trigger,
                NextState('IDLE'),
            )
        )
