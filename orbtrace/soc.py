from migen import *

from litex.soc.integration.soc_core import SoCCore

from .trace import TraceCore

from .nmigen_glue.wrapper import Wrapper
from .nmigen_glue.luna import USBDevice, USBStreamOutEndpoint, USBStreamInEndpoint, USBMultibyteStreamInEndpoint
from .nmigen_glue.usb_mem_bridge import MemRequestHandler

from usb_protocol.emitters   import DeviceDescriptorCollection
from usb_protocol.emitters.descriptors import cdc

from litex.soc.interconnect import stream
from litex.soc.interconnect.stream import Endpoint, Pipeline, AsyncFIFO, ClockDomainCrossing, Converter
from litex.soc.interconnect.axi import AXILiteInterface, AXILiteClockDomainCrossing

class USBAllocator:
    def __init__(self):
        self._next_interface = 0
        self._next_in_ep     = 1
        self._next_out_ep    = 1
    
    def interface(self):
        n = self._next_interface
        self._next_interface += 1
        return n
    
    def in_ep(self):
        n = self._next_in_ep
        self._next_in_ep += 1
        return n
    
    def out_ep(self):
        n = self._next_out_ep
        self._next_out_ep += 1
        return n

class OrbSoC(SoCCore):
    def __init__(self, platform, sys_clk_freq, **kwargs):

        # SoCCore
        SoCCore.__init__(self, platform, sys_clk_freq,
            ident          = 'LiteX SoC for Orbtrace',
            ident_version  = True,
            **kwargs)

        # CRG
        self.submodules.crg = platform.get_crg(sys_clk_freq)

        # nMigen wrapper
        self.add_wrapper()

        # LEDs
        if hasattr(platform, 'add_leds'):
            platform.add_leds(self)
        
        if hasattr(self, 'led_status'):
            self.comb += self.led_status.g.eq(1)

        # USB
        self.add_usb()

        # USB UART
        if kwargs['uart_name'] == 'stream':
            self.add_usb_uart(self.uart)

        # USB Bridge
        self.add_usb_bridge()

        # Trace
        self.add_trace()

        # USB
        self.finalize_usb()

    def add_trace(self):
        # Trace core.
        self.submodules.trace = TraceCore(self.platform)

        # LEDs
        if hasattr(self, 'led_trace'):
            self.comb += self.led_trace.r.eq(self.trace.loss)

        # USB interface.
        if_num = self.usb_alloc.interface()
        ep_num = self.usb_alloc.in_ep()

        # USB descriptors.
        with self.usb_conf_desc.InterfaceDescriptor() as i:
            i.bInterfaceNumber   = if_num
            i.bInterfaceClass    = 0xff
            i.bInterfaceSubclass = 0x54
            i.bInterfaceProtocol = 0x01

            i.iInterface = 'Trace (TPIU)'

            with i.EndpointDescriptor() as e:
                e.bEndpointAddress = 0x80 | ep_num
                e.wMaxPacketSize   = 512

        # Endpoint handler.
        ep = USBMultibyteStreamInEndpoint(
            endpoint_number = ep_num,
            max_packet_size = 512,
            byte_width = 16,
        )
        self.usb.add_endpoint(ep)

        cdc = ClockDomainCrossing(ep.sink.description, 'sys', 'usb')

        pipeline = Pipeline(self.trace, cdc, ep)
        self.submodules += cdc, pipeline

    def add_usb_uart(self, uart):
        comm_if = self.usb_alloc.interface()
        comm_ep = self.usb_alloc.in_ep()

        data_if     = self.usb_alloc.interface()
        data_in_ep  = self.usb_alloc.in_ep()
        data_out_ep = self.usb_alloc.out_ep()

        # Communications interface descriptor.
        with self.usb_conf_desc.InterfaceDescriptor() as i:
            i.bInterfaceNumber   = comm_if
            i.bInterfaceClass    = 0x02 # CDC
            i.bInterfaceSubclass = 0x02 # ACM
            i.bInterfaceProtocol = 0x01 # AT commands / UART

            i.add_subordinate_descriptor(cdc.HeaderDescriptorEmitter())

            union = cdc.UnionFunctionalDescriptorEmitter()
            union.bControlInterface      = comm_if
            union.bSubordinateInterface0 = data_if
            i.add_subordinate_descriptor(union)

            call_management = cdc.CallManagementFunctionalDescriptorEmitter()
            call_management.bDataInterface = data_if
            i.add_subordinate_descriptor(call_management)

            with i.EndpointDescriptor() as e:
                e.bEndpointAddress = 0x80 | comm_ep
                e.bmAttributes     = 0x03
                e.wMaxPacketSize   = 512
                e.bInterval        = 11

        # Data interface descriptor.
        with self.usb_conf_desc.InterfaceDescriptor() as i:
            i.bInterfaceNumber   = data_if
            i.bInterfaceClass    = 0x0a # CDC data
            i.bInterfaceSubclass = 0x00
            i.bInterfaceProtocol = 0x00

            with i.EndpointDescriptor() as e:
                e.bEndpointAddress = 0x80 | data_in_ep
                e.wMaxPacketSize   = 512

            with i.EndpointDescriptor() as e:
                e.bEndpointAddress = data_out_ep
                e.wMaxPacketSize   = 512

        # Endpoint handlers.
        in_ep = USBStreamInEndpoint(
            endpoint_number = data_in_ep,
            max_packet_size = 512,
        )
        self.usb.add_endpoint(in_ep)

        out_ep = USBStreamOutEndpoint(
            endpoint_number = data_out_ep,
            max_packet_size = 512,
        )
        self.usb.add_endpoint(out_ep)

        # Stream CDC.
        in_cdc = ClockDomainCrossing(in_ep.sink.description, 'sys', 'usb')
        out_cdc = ClockDomainCrossing(out_ep.source.description, 'usb', 'sys')

        pipeline = Pipeline(out_ep, out_cdc, uart, in_cdc, in_ep)

        self.submodules += in_cdc, out_cdc, pipeline

    def add_usb_bridge(self):
        mem_request_handler = MemRequestHandler()

        self.add_usb_control_handler(mem_request_handler.handler) # FIXME: wrap

        mem_request_handler.wrap(self.usb.wrapper) # FIXME: wrap

        axi_lite = AXILiteInterface()

        self.submodules += AXILiteClockDomainCrossing(mem_request_handler.axi_lite, axi_lite, 'usb', 'sys')

        self.bus.add_master('usb_bridge', axi_lite)

    def add_usb_control_handler(self, handler):
        if hasattr(self, 'usb_control_ep'):
            self.usb_control_ep.add_request_handler(handler)
        
        else:
            self.usb_control_handlers.append(handler)

    def add_usb(self):            
        self.usb_alloc = USBAllocator()

        self.wrapper.connect_domain('usb')

        self.submodules.usb = USBDevice(self.platform.request('ulpi'), wrapper = self.wrapper)

        self.usb_descriptors = DeviceDescriptorCollection()

        with self.usb_descriptors.DeviceDescriptor() as d:
            d.idVendor           = 0x1209
            d.idProduct          = 0x3443  # Allocated from pid.codes

            d.iManufacturer      = "Orbcode"
            d.iProduct           = "Orbtrace"
            #d.iSerialNumber      = ""

            d.bNumConfigurations = 1
        
        self.usb_conf_emitter = self.usb_descriptors.ConfigurationDescriptor()

        # Enter ConfigurationDescriptor context manager to avoid having to wrap everything in a with-statement.
        self.usb_conf_desc = self.usb_conf_emitter.__enter__()

        self.usb_control_handlers = []

    def finalize_usb(self):
        # Exit ConfigurationDescriptor context manager to emit configuration descriptor.
        self.usb_conf_emitter.__exit__(None, None, None)

        # Delete this since it's too late to add more interfaces.
        del self.usb_conf_desc

        # Add control endpoint handler.
        self.usb_control_ep = self.usb.usb.add_standard_control_endpoint(self.usb_descriptors) # FIXME: wrap
        
        # Add additional request handlers.
        for handler in self.usb_control_handlers:
            self.usb_control_ep.add_request_handler(handler)
        
    def add_wrapper(self):
        self.submodules.wrapper = Wrapper(self.platform)

        self.wrapper.connect_domain('sys')
