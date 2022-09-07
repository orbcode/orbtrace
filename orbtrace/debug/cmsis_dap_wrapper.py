from migen import *

import amaranth
from amaranth.hdl.rec import DIR_FANIN, DIR_FANOUT, DIR_NONE

from luna.gateware.stream import StreamInterface

from . import cmsis_dap, dbgIF, dbgIF_wrapper

from litex.soc.interconnect.stream import Endpoint

from litex.build.io import SDRInput, DDRInput, SDROutput, SDRTristate

class CMSIS_DAP(Module):
    def __init__(self, dbgif, wrapper):
        self.source = Endpoint([('data', 8)])
        self.sink = Endpoint([('data', 8)])
        self.is_v2 = Signal()
        self.can = Signal()
        self.connected = Signal()
        self.running = Signal()

        stream_in = StreamInterface()
        stream_out = StreamInterface()

        is_v2 = amaranth.Signal()

        dbgif_wrapper = dbgIF_wrapper.DBGIF(dbgif, wrapper)
        wrapper.m.submodules += dbgif_wrapper

        dap = cmsis_dap.CMSIS_DAP(stream_in, stream_out, dbgif_wrapper, is_v2)
        wrapper.m.submodules += dap

        wrapper.connect(self.source.data, stream_in.payload)
        wrapper.connect(self.source.first, stream_in.first)
        wrapper.connect(self.source.last, stream_in.last)
        wrapper.connect(self.source.valid, stream_in.valid)
        wrapper.connect(self.source.ready, stream_in.ready)

        wrapper.connect(self.sink.data, stream_out.payload)
        wrapper.connect(self.sink.first, stream_out.first)
        wrapper.connect(self.sink.last, stream_out.last)
        wrapper.connect(self.sink.valid, stream_out.valid)
        wrapper.connect(self.sink.ready, stream_out.ready)

        wrapper.connect(self.is_v2, is_v2)

        wrapper.connect(self.can, dap.can)

        wrapper.connect(self.connected, dap.connected)
        wrapper.connect(self.running, dap.running)
