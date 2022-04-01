from migen import *

from litespi.common import spi_core2phy_layout, spi_phy2core_layout

from litex.soc.interconnect.stream import Endpoint
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus

UID_CMD = 0x4b

class FlashUID(Module, AutoCSR):
    def __init__(self, uid_bytes = 8, dummy_bytes = 4):
        # PHY interface
        self.phy_source = phy_source = Endpoint(spi_core2phy_layout)
        self.phy_sink = phy_sink = Endpoint(spi_phy2core_layout)
        self.cs = cs = Signal()
        self.request = request = Signal()

        # UID signals
        self.valid = Signal()
        self.uid = Signal(uid_bytes * 8)

        # CSRs
        self._valid = CSRStatus()
        self._uid = CSRStatus(uid_bytes * 8)

        self.comb += [
            self._valid.status.eq(self.valid),
            self._uid.status.eq(self.uid),
        ]

        read_cnt = Signal(max = 1 + uid_bytes + dummy_bytes)

        self.submodules.fsm = fsm = FSM()

        self.comb += [
            phy_source.data.eq(UID_CMD),
            phy_source.len.eq(8),
            phy_source.width.eq(1),
            phy_source.mask.eq(1),
        ]

        fsm.act('INIT',
            NextState('WRITE'),
            NextValue(read_cnt, uid_bytes + dummy_bytes),
        )

        fsm.act('WRITE',
            cs.eq(1),
            request.eq(1),

            phy_source.valid.eq(1),

            If(phy_source.ready,
                NextState('READ'),
            ),
        )

        fsm.act('READ',
            cs.eq(1),
            request.eq(1),

            phy_sink.ready.eq(1),

            If(phy_sink.valid,
                NextValue(self.uid, Cat(phy_sink.data[:8], self.uid[:-8])),
                If(read_cnt,
                    NextState('WRITE'),
                    NextValue(read_cnt, read_cnt - 1),
                ).Else(
                    NextState('DONE'),
                ),
            ),
        )

        fsm.act('DONE',
            self.valid.eq(1),
        )
