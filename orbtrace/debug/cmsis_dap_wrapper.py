from migen import *

from amaranth.lib import wiring

from . import cmsis_dap, dbgIF_wrapper

from litex.soc.interconnect.stream import Endpoint

class CMSIS_DAP(Module):
    def __init__(self, dbgif, glue):
        self.source = Endpoint([('data', 8)])
        self.sink = Endpoint([('data', 8)])
        self.is_v2 = Signal()
        self.can = Signal()
        self.connected = Signal()
        self.running = Signal()

        dbgif_wrapper = dbgIF_wrapper.DBGIF(dbgif, glue)
        glue.m.submodules += dbgif_wrapper

        dap = cmsis_dap.CMSIS_DAP()
        glue.m.submodules += dap

        wiring.connect(glue.m, dbgif_wrapper, dap.dbgif)

        glue.connect(self.source.data, dap.streamIn.data)
        glue.connect(self.source.first, dap.streamIn.first)
        glue.connect(self.source.last, dap.streamIn.last)
        glue.connect(self.source.valid, dap.streamIn.valid)
        glue.connect(self.source.ready, dap.streamIn.ready)

        glue.connect(self.sink.data, dap.streamOut.data)
        glue.connect(self.sink.first, dap.streamOut.first)
        glue.connect(self.sink.last, dap.streamOut.last)
        glue.connect(self.sink.valid, dap.streamOut.valid)
        glue.connect(self.sink.ready, dap.streamOut.ready)

        glue.connect(self.is_v2, dap.isV2)

        glue.connect(self.can, dap.can)

        glue.connect(self.connected, dap.connected)
        glue.connect(self.running, dap.running)
