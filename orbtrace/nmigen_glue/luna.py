from .wrapper import Wrapper

import nmigen
import migen

import luna.usb2
from luna.gateware.architecture.car import PHYResetController

from litex.soc.interconnect.stream import Endpoint

class USBDevice(migen.Module):
    def __init__(self, pads, wrapper, *args, **kwargs):
        self.wrapper = wrapper

        phy_reset_controller = PHYResetController()
        wrapper.m.submodules += phy_reset_controller

        wrapper.m.d.comb += [
            nmigen.ResetSignal('usb').eq(phy_reset_controller.phy_reset),
        ]

        ulpi_data = migen.TSTriple(8)
        ulpi_rst = migen.Signal()

        self.specials += ulpi_data.get_tristate(pads.data)

        if hasattr(pads, 'rst'):
            self.comb += pads.rst.eq(ulpi_rst)
        elif hasattr(pads, 'rst_n'):
            self.comb += pads.rst_n.eq(~ulpi_rst)

        if hasattr(pads, 'clk'):
            self.clock_domains.usb = migen.ClockDomain()

        from nmigen.hdl.rec import DIR_FANIN, DIR_FANOUT, DIR_NONE
        ulpi = nmigen.Record(
            [
                ('data', [('i', 8, DIR_FANIN), ('o', 8, DIR_FANOUT), ('oe', 1, DIR_FANOUT)]),
                ('clk', [('i', 1, DIR_FANIN)] if hasattr(pads, 'clk') else [('o', 1, DIR_FANOUT)]),
                ('stp', 1, DIR_FANOUT),
                ('nxt', [('i', 1, DIR_FANIN)]),
                ('dir', [('i', 1, DIR_FANIN)]),
                ('rst', 1, DIR_FANOUT),
            ],
        )

        wrapper.connect(ulpi_data.i, ulpi.data.i)
        wrapper.connect(ulpi_data.o, ulpi.data.o)
        wrapper.connect(ulpi_data.oe, ulpi.data.oe)

        wrapper.connect(pads.stp, ulpi.stp)
        wrapper.connect(pads.nxt, ulpi.nxt.i)
        wrapper.connect(pads.dir, ulpi.dir.i)
        wrapper.connect(ulpi_rst, ulpi.rst)

        if hasattr(pads, 'clk'):
            wrapper.connect(pads.clk, ulpi.clk.i)
        else:
            wrapper.connect(pads.clk_o, ulpi.clk.o)

        self.usb = luna.usb2.USBDevice(bus = ulpi, *args, **kwargs)
        wrapper.m.submodules += self.usb

        wrapper.m.d.comb += [
            self.usb.connect.eq(1),
        ]

    def add_endpoint(self, ep):
        self.usb.add_endpoint(ep._ep)
        ep.wrap(self.wrapper)

class USBStreamOutEndpoint:
    def __init__(self, *, endpoint_number, **kwargs):
        self._ep = luna.usb2.USBStreamOutEndpoint(endpoint_number = endpoint_number, **kwargs)

        self.source = Endpoint([('data', 8)])
    
    def wrap(self, wrapper):
        wrapper.connect(self.source.data, self._ep.stream.payload)
        wrapper.connect(self.source.first, self._ep.stream.first)
        wrapper.connect(self.source.last, self._ep.stream.last)
        wrapper.connect(self.source.valid, self._ep.stream.valid)
        wrapper.connect(self.source.ready, self._ep.stream.ready)

class USBStreamInEndpoint:
    def __init__(self, *, endpoint_number, **kwargs):
        self._ep = luna.usb2.USBStreamInEndpoint(endpoint_number = endpoint_number, **kwargs)

        self.sink = Endpoint([('data', 8)])
    
    def wrap(self, wrapper):
        wrapper.connect(self.sink.data, self._ep.stream.payload)
        wrapper.connect(self.sink.first, self._ep.stream.first)
        wrapper.connect(self.sink.last, self._ep.stream.last)
        wrapper.connect(self.sink.valid, self._ep.stream.valid)
        wrapper.connect(self.sink.ready, self._ep.stream.ready)

class USBMultibyteStreamInEndpoint:
    def __init__(self, *, endpoint_number, byte_width, **kwargs):
        self._ep = luna.usb2.USBMultibyteStreamInEndpoint(endpoint_number = endpoint_number, byte_width = byte_width, **kwargs)

        self.sink = Endpoint([('data', 8 * byte_width)])
    
    def wrap(self, wrapper):
        wrapper.connect(self.sink.data, self._ep.stream.payload)
        wrapper.connect(self.sink.first, self._ep.stream.first)
        wrapper.connect(self.sink.last, self._ep.stream.last)
        wrapper.connect(self.sink.valid, self._ep.stream.valid)
        wrapper.connect(self.sink.ready, self._ep.stream.ready)
