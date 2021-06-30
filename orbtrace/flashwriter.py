from migen import *

from litespi.common import spi_phy_ctl_layout, spi_phy_data_layout, USER

from litex.soc.interconnect.stream import Endpoint

PROGRAM_SIZE = 256

#ERASE_CMD = 0x20
#ERASE_SIZE = 4096

ERASE_CMD = 0xd8
ERASE_SIZE = 65536

class FlashWriter(Module):
    def __init__(self):
        # PHY interface
        self.phy_source = phy_source = Endpoint(spi_phy_ctl_layout)
        self.phy_sink = phy_sink = Endpoint(spi_phy_data_layout)
        self.cs = cs = Signal()
        self.request = request = Signal()

        # Write interface
        self.sink = sink = Endpoint([('data', 8), ('addr', 24)])

        self.comb += [
            phy_source.cmd.eq(USER),
        ]

        erase_required = sink.addr & (ERASE_SIZE - 1) == 0
        erase_done = Signal()
        program_done = Signal()

        self.submodules.fsm = fsm = FSM()

        fsm.act('IDLE',
            If(sink.valid,
                NextState('WREN'),
            )
        )

        fsm.act('WREN',
            cs.eq(1),
            request.eq(1),

            phy_source.data.eq(0x06),
            phy_source.len.eq(8),
            phy_source.width.eq(1),
            phy_source.mask.eq(1),
            phy_source.valid.eq(1),

            If(phy_source.ready,
                NextState('WREN_WAIT'),
            ),
        )

        fsm.act('WREN_WAIT',
            cs.eq(1),
            request.eq(1),

            phy_sink.ready.eq(1),

            If(phy_sink.valid,
                cs.eq(0),

                If(erase_required & ~erase_done,
                    NextState('ERASE'),
                    NextValue(erase_done, 1)
                ).Else(
                    NextState('PROGRAM'),
                    NextValue(erase_done, 0)
                )
            ),
        )

        fsm.act('ERASE',
            cs.eq(1),
            request.eq(1),

            phy_source.data.eq(Cat(sink.addr, ERASE_CMD)),
            phy_source.len.eq(8 + 24),
            phy_source.width.eq(1),
            phy_source.mask.eq(1),
            phy_source.valid.eq(1),

            If(phy_source.ready,
                NextState('ERASE_WAIT'),
            ),
        )

        fsm.act('ERASE_WAIT',
            cs.eq(1),
            request.eq(1),

            phy_sink.ready.eq(1),

            If(phy_sink.valid,
                cs.eq(0),

                NextState('READ_STATUS'),
            ),
        )

        fsm.act('READ_STATUS',
            cs.eq(1),
            request.eq(1),

            phy_source.data.eq(0x0500),
            phy_source.len.eq(16),
            phy_source.width.eq(1),
            phy_source.mask.eq(1),
            phy_source.valid.eq(1),

            If(phy_source.ready,
                NextState('READ_STATUS_WAIT'),
            ),
        )

        fsm.act('READ_STATUS_WAIT',
            cs.eq(1),
            request.eq(1),

            phy_sink.ready.eq(1),

            If(phy_sink.valid,
                cs.eq(0),

                If(phy_sink.data[0],
                    NextState('READ_STATUS'),
                ).Elif(sink.valid,
                    NextState('WREN'),
                ).Else(
                    NextState('IDLE'),
                ),
            ),
        )

        fsm.act('PROGRAM',
            cs.eq(1),
            request.eq(1),

            phy_source.data.eq(Cat(sink.addr, 0x02)),
            phy_source.len.eq(8 + 24),
            phy_source.width.eq(1),
            phy_source.mask.eq(1),
            phy_source.valid.eq(1),

            If(phy_source.ready,
                NextState('PROGRAM_DATA'),
            ),
        )

        fsm.act('PROGRAM_DATA',
            cs.eq(1),
            request.eq(1),

            phy_source.data.eq(sink.data),
            phy_source.len.eq(8),
            phy_source.width.eq(1),
            phy_source.mask.eq(1),
            phy_source.valid.eq(sink.valid),
            sink.ready.eq(phy_source.ready),

            phy_sink.ready.eq(1),

            If(sink.valid & sink.ready & (sink.last | (sink.addr & (PROGRAM_SIZE - 1) == (PROGRAM_SIZE - 1))),
                NextState('PROGRAM_WAIT'),
            ),
        )

        fsm.act('PROGRAM_WAIT',
            cs.eq(1),
            request.eq(1),

            phy_sink.ready.eq(1),

            If(program_done,
                cs.eq(0),

                NextState('READ_STATUS'),
            ),
        )

        outstanding_transfers = Signal(max = PROGRAM_SIZE + 2)
        transfer_out = phy_source.valid & phy_source.ready
        transfer_in = phy_sink.valid & phy_sink.ready

        self.sync += [
            If(fsm.ongoing('PROGRAM'),
                outstanding_transfers.eq(1),
            ),
            If(fsm.ongoing('PROGRAM_DATA') | fsm.ongoing('PROGRAM_WAIT'),
                If(transfer_out & ~transfer_in,
                    outstanding_transfers.eq(outstanding_transfers + 1),
                ),
                If(~transfer_out & transfer_in,
                    outstanding_transfers.eq(outstanding_transfers - 1),
                ),
            ),
        ]

        self.comb += program_done.eq(outstanding_transfers == 0)
