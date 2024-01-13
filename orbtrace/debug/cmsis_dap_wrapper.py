from migen import *

import amaranth
from amaranth.hdl.rec import DIR_FANIN, DIR_FANOUT, DIR_NONE

from luna.gateware.stream import StreamInterface

from . import cmsis_dap, dbgIF, dbgIF_wrapper

from litex.soc.interconnect.stream import Endpoint

from litex.build.io import SDRInput, DDRInput, SDROutput, SDRTristate

class CMSIS_DAP(Module):
    def __init__(self, dbgif, glue):
        self.source = Endpoint([('data', 8)])
        self.sink = Endpoint([('data', 8)])
        self.is_v2 = Signal()
        self.can = Signal()
        self.connected = Signal()
        self.running = Signal()

        stream_in = StreamInterface()
        stream_out = StreamInterface()

        is_v2 = amaranth.Signal()

        dbgif_wrapper = dbgIF_wrapper.DBGIF(dbgif, glue)
        glue.m.submodules += dbgif_wrapper

        dap = cmsis_dap.CMSIS_DAP(stream_in, stream_out, dbgif_wrapper, is_v2)
        glue.m.submodules += dap

        glue.connect(self.source.data, stream_in.payload)
        glue.connect(self.source.first, stream_in.first)
        glue.connect(self.source.last, stream_in.last)
        glue.connect(self.source.valid, stream_in.valid)
        glue.connect(self.source.ready, stream_in.ready)

        glue.connect(self.sink.data, stream_out.payload)
        glue.connect(self.sink.first, stream_out.first)
        glue.connect(self.sink.last, stream_out.last)
        glue.connect(self.sink.valid, stream_out.valid)
        glue.connect(self.sink.ready, stream_out.ready)

        glue.connect(self.is_v2, is_v2)

        glue.connect(self.can, dap.can)

        glue.connect(self.connected, dap.connected)
        glue.connect(self.running, dap.running)
