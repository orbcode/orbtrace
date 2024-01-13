import amaranth

from litex.soc.interconnect.stream import Endpoint

from .. import dfu

class DFUHandler:
    def __init__(self, if_num, areas):
        self.source = Endpoint([('data', 8), ('addr', 24)])

        self.handler = dfu.DFUHandler(if_num, areas)
    
    def wrap(self, glue):
        glue.connect(self.source.data, self.handler.source.data)
        glue.connect(self.source.addr, self.handler.source.addr)
        glue.connect(self.source.valid, self.handler.source.valid)
        glue.connect(self.source.ready, self.handler.source.ready)
        glue.connect(self.source.first, self.handler.source.first)
        glue.connect(self.source.last, self.handler.source.last)
