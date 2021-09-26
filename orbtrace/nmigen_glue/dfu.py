import nmigen

from litex.soc.interconnect.stream import Endpoint

from .. import dfu

class DFUHandler:
    def __init__(self, if_num, areas):
        self.source = Endpoint([('data', 8), ('addr', 24)])

        self.handler = dfu.DFUHandler(if_num, areas)
    
    def wrap(self, wrapper):
        wrapper.connect(self.source.data, self.handler.source.data)
        wrapper.connect(self.source.addr, self.handler.source.addr)
        wrapper.connect(self.source.valid, self.handler.source.valid)
        wrapper.connect(self.source.ready, self.handler.source.ready)
        wrapper.connect(self.source.first, self.handler.source.first)
        wrapper.connect(self.source.last, self.handler.source.last)
