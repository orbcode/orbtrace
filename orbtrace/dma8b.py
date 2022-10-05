from migen import *

from litex.soc.interconnect import wishbone

class DMA8b(Module):
    def __init__(self, mem_size):
        self.masters = []

        self.bus = wishbone.Interface()
        self.submodules += wishbone.DownConverter(self.bus, self.get_master_port())

        self.mem_bus = wishbone.Interface(8, 32)
        self.submodules += wishbone.SRAM(mem_size, bus = self.mem_bus)

    def get_master_port(self):
        bus = wishbone.Interface(8, 32)
        self.masters.append(bus)
        return bus
    
    def do_finalize(self):
        self.submodules += wishbone.Arbiter(self.masters, self.mem_bus)
