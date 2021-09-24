from migen import *

from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.soc import SoCRegion

from .trace import TraceCore

from .nmigen_glue.wrapper import Wrapper
from .nmigen_glue.luna import USBDevice, USBStreamOutEndpoint, USBStreamInEndpoint, USBMultibyteStreamInEndpoint
from .nmigen_glue.usb_mem_bridge import MemRequestHandler
from .nmigen_glue.cmsis_dap import CMSIS_DAP
from .nmigen_glue.dfu import DFUHandler

from .flashwriter import FlashWriter

from .led_ctrl import LEDCtrl

from usb_protocol.types      import USBTransferType, USBRequestType, USBStandardRequests
from usb_protocol.emitters   import DeviceDescriptorCollection
from usb_protocol.emitters.descriptors import cdc

from litex.soc.interconnect import stream
from litex.soc.interconnect.stream import Endpoint, Pipeline, AsyncFIFO, ClockDomainCrossing, Converter, Multiplexer, Demultiplexer
from litex.soc.interconnect.axi import AXILiteInterface, AXILiteClockDomainCrossing

from litespi.phy.generic import LiteSPIPHY
from litespi import LiteSPI

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
    def __init__(self, platform, sys_clk_freq, with_debug, with_trace, with_dfu, usb_vid, usb_pid, led_default, bootloader_auto_reset, **kwargs):

        # SoCCore
        SoCCore.__init__(self, platform, sys_clk_freq,
            ident          = 'LiteX SoC for Orbtrace',
            ident_version  = True,
            **kwargs)

        # CRG
        self.submodules.crg = platform.get_crg(sys_clk_freq)

        # Flash
        self.add_flash()

        # nMigen wrapper
        self.add_wrapper()

        # LEDs
        self.add_leds(led_default)

        # Bootloader auto reset
        if bootloader_auto_reset:
            self.add_auto_reset()

        # USB
        self.add_usb(usb_vid, usb_pid)

        # USB UART
        if kwargs['uart_name'] == 'stream':
            self.add_usb_uart(self.uart)

        # USB Bridge
        self.add_usb_bridge()

        # Trace
        if with_trace:
            self.add_trace()

        # Debug
        if with_debug:
            self.add_debug()

        # Target power
        #self.add_target_power()

        # Platform specific
        self.add_platform_specific()

        # DFU
        if with_dfu:
            self.add_dfu(with_dfu)

        # USB
        self.finalize_usb()

    def add_auto_reset(self):
        programn = self.platform.request('programn')
        btn = self.platform.request('btn')

        reset_set = Signal()
        reset = Signal()

        self.sync += If(~reset_set,
            reset_set.eq(1),
            reset.eq(btn), # Button is active low, reset if button is not pressed
        )

        self.comb += programn.eq(~reset)

    def add_leds(self, default):
        if hasattr(self.platform, 'add_leds'):
            self.platform.add_leds(self)

        self.submodules.led_ctrl = LEDCtrl(5, default)

        for i, n in enumerate(['led_status', 'led_debug', 'led_trace', 'led_vtref', 'led_vtpwr']):
            if not hasattr(self, n):
                continue

            self.comb += getattr(self, n).eq(self.led_ctrl.outputs[i])
            setattr(self, n, self.led_ctrl.inputs[i])

    def add_flash(self):
        if not hasattr(self.platform, 'get_flash_module'):
            return

        flash = self.platform.get_flash_module()
        #flash = S25FL064L(Codes.READ_1_4_4)

        self.submodules.spiflash_phy = LiteSPIPHY(
            pads = self.platform.request('spiflash4x'),
            flash = flash,
            device = self.platform.device,
        )
        self.add_csr('spiflash_phy')

        self.submodules.spiflash_mmap = LiteSPI(
            phy = self.spiflash_phy,
            clk_freq = self.sys_clk_freq,
            mmap_endianness = self.cpu.endianness,
        )
        self.add_csr('spiflash_mmap')

        spiflash_region = SoCRegion(
            origin = self.mem_map.get('spiflash', 0x08000000),
            size = flash.total_size,
            mode = 'r',
        )

        self.bus.add_slave(
            name = 'spiflash',
            slave = self.spiflash_mmap.bus,
            region = spiflash_region,
        )

    def add_target_power(self):
        pads = self.platform.request('target_power')

        self.comb += [
            pads.vtref_en_n.eq(1),
            pads.vtpwr_en_n.eq(0),
        ]

    def add_debug(self, with_v1 = True, with_v2 = True):
        # Add verilog sources.
        self.platform.add_source('verilog/dbgIF.v')
        self.platform.add_source('verilog/swdIF.v')
        self.platform.add_source('verilog/jtagIF.v')

        # CMSIS-DAP.
        self.submodules.cmsis_dap = CMSIS_DAP(self.platform.request('debug'), wrapper = self.wrapper)

        if with_v1:
            # USB interface.
            if_num = self.usb_alloc.interface()
            in_ep_num = self.usb_alloc.in_ep()
            out_ep_num = self.usb_alloc.out_ep()

            # USB descriptors.
            with self.usb_conf_desc.InterfaceDescriptor() as i:
                i.bInterfaceNumber   = if_num
                i.bInterfaceClass    = 0x03
                i.bInterfaceSubclass = 0x00
                i.bInterfaceProtocol = 0x00

                i.iInterface = 'CMSIS-DAP v1'

                # This is the HID descriptor
                i.add_subordinate_descriptor(b"\x09\x21\x11\x01\x00\x01\x22\x21\x00")
                self.usb_descriptors.add_descriptor(b"\x06\x00\xFF\x09\x01\xA1\x01\x15\x00\x26\xFF\x00\x75\x08\x95\x40\x09\x01\x81"
                                                    b"\x02\x95\x40\x09\x01\x91\x02\x95\x01\x09\x01\xB1\x02\xC0", descriptor_type=0x22)

                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = 0x80 | in_ep_num
                    e.wMaxPacketSize   = 64
                    e.bmAttributes     = USBTransferType.INTERRUPT
                    e.bInterval        = 1

                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = out_ep_num
                    e.wMaxPacketSize   = 64
                    e.bmAttributes     = USBTransferType.INTERRUPT
                    e.bInterval        = 1

            # Endpoint handlers.
            in_ep_v1 = USBStreamInEndpoint(
                endpoint_number = in_ep_num,
                max_packet_size = 64,
            )
            self.usb.add_endpoint(in_ep_v1)

            out_ep_v1 = USBStreamOutEndpoint(
                endpoint_number = out_ep_num,
                max_packet_size = 65, # Workaround for interrupt. TODO: Revert to 64 after this has been fixed in LUNA.
            )
            self.usb.add_endpoint(out_ep_v1)

        if with_v2:
            # USB interface.
            if_num = self.usb_alloc.interface()
            in_ep_num = self.usb_alloc.in_ep()
            out_ep_num = self.usb_alloc.out_ep()

            # USB descriptors.
            with self.usb_conf_desc.InterfaceDescriptor() as i:
                i.bInterfaceNumber   = if_num
                i.bInterfaceClass    = 0xff
                i.bInterfaceSubclass = 0
                i.bInterfaceProtocol = 0

                i.iInterface = 'CMSIS-DAP v2'

                # CMSIS-DAPv2 endpoints need to be in a specific order...
                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = out_ep_num
                    e.wMaxPacketSize   = 512

                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = 0x80 | in_ep_num
                    e.wMaxPacketSize   = 512

            # Endpoint handlers.
            in_ep_v2 = USBStreamInEndpoint(
                endpoint_number = in_ep_num,
                max_packet_size = 512,
            )
            self.usb.add_endpoint(in_ep_v2)

            out_ep_v2 = USBStreamOutEndpoint(
                endpoint_number = out_ep_num,
                max_packet_size = 512,
            )
            self.usb.add_endpoint(out_ep_v2)

        # Stream CDC.
        stream_desc = [('data', 8)]

        in_stream = Endpoint(stream_desc)
        out_stream = Endpoint(stream_desc)

        in_cdc = ClockDomainCrossing(stream_desc, 'sys', 'usb')
        out_cdc = ClockDomainCrossing(stream_desc, 'usb', 'sys')

        pipeline = Pipeline(out_stream, out_cdc, self.cmsis_dap, in_cdc, in_stream)

        self.submodules += in_cdc, out_cdc, pipeline

        # Interface mux.
        is_v2 = Signal()
        self.comb += self.cmsis_dap.is_v2.eq(is_v2)

        can = self.platform.request('gpio', 0)
        self.comb += can.data.eq(self.cmsis_dap.can)
        if hasattr(can, 'dir'):
            self.comb += can.dir.eq(1)

        if with_v1 and with_v2:
            out_mux = Multiplexer(stream_desc, 2)
            in_demux = Demultiplexer(stream_desc, 2)

            self.comb += [
                out_ep_v1.source.connect(out_mux.sink0),
                out_ep_v2.source.connect(out_mux.sink1),
                out_mux.source.connect(out_stream),
                out_mux.sel.eq(is_v2),

                in_stream.connect(in_demux.sink),
                in_demux.source0.connect(in_ep_v1.sink),
                in_demux.source1.connect(in_ep_v2.sink),
                in_demux.sel.eq(is_v2),
            ]

            self.sync.usb += [
                If(out_ep_v1.source.valid,
                    is_v2.eq(0),
                ),
                If(out_ep_v2.source.valid,
                    is_v2.eq(1),
                ),
            ]

            self.submodules += out_mux, in_demux

        elif with_v1:
            self.comb += [
                out_ep_v1.source.connect(out_stream),
                in_stream.connect(in_ep_v1.sink),
                is_v2.eq(0),
            ]

        elif with_v2:
            self.comb += [
                out_ep_v2.source.connect(out_stream),
                in_stream.connect(in_ep_v2.sink),
                is_v2.eq(1),
            ]

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
        pipeline.comb += in_ep.sink.last.eq(1)

        self.submodules += in_cdc, out_cdc, pipeline

    def add_usb_bridge(self):
        mem_request_handler = MemRequestHandler()

        self.add_usb_control_handler(mem_request_handler.handler) # FIXME: wrap

        mem_request_handler.wrap(self.usb.wrapper) # FIXME: wrap

        axi_lite = AXILiteInterface()

        self.submodules += AXILiteClockDomainCrossing(mem_request_handler.axi_lite, axi_lite, 'usb', 'sys')

        self.bus.add_master('usb_bridge', axi_lite)

    def add_dfu(self, mode):
        dfu_if = self.usb_alloc.interface()

        # DFU interface descriptor.
        with self.usb_conf_desc.InterfaceDescriptor() as i:
            i.bInterfaceNumber   = dfu_if
            i.bInterfaceClass    = 0xfe # Application specific class
            i.bInterfaceSubclass = 0x01 # DFU
            i.bInterfaceProtocol = 0x01 if mode == 'runtime' else 0x02 # Mode

            # DFU functional descriptor
            i.add_subordinate_descriptor(b'\x09\x21\x0d\x00\x00\x00\x01\x00\x01')

        dfu_handler = DFUHandler(dfu_if)

        self.add_usb_control_handler(dfu_handler.handler) # FIXME: wrap

        dfu_handler.wrap(self.wrapper)

        self.submodules.flashwriter = FlashWriter()

        port = self.spiflash_mmap.crossbar.get_port(self.flashwriter.cs, self.flashwriter.request)

        self.comb += [
            self.flashwriter.phy_source.connect(port.sink),
            port.source.connect(self.flashwriter.phy_sink),
        ]

        cdc = ClockDomainCrossing(dfu_handler.source.description, 'usb', 'sys')

        pipeline = Pipeline(dfu_handler, cdc, self.flashwriter)

        self.submodules += cdc, pipeline

    def add_usb_control_handler(self, handler):
        if hasattr(self, 'usb_control_ep'):
            self.usb_control_ep.add_request_handler(handler)

        else:
            self.usb_control_handlers.append(handler)

    def add_usb(self, vid, pid):
        self.usb_alloc = USBAllocator()

        self.wrapper.connect_domain('usb')

        self.submodules.usb = USBDevice(self.platform.request('ulpi'), wrapper = self.wrapper)

        self.usb_descriptors = DeviceDescriptorCollection()

        with self.usb_descriptors.DeviceDescriptor() as d:
            d.idVendor           = vid
            d.idProduct          = pid

            d.iManufacturer      = "Orbcode"
            d.iProduct           = "Orbtrace Bootloader" if pid == 0x3442 else "Orbtrace Test" if pid == 0x0001 else "Orbtrace"
            d.iSerialNumber      = "N/A"

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

        blacklist = [lambda setup: (setup.type == USBRequestType.STANDARD) & (setup.request == USBStandardRequests.SET_INTERFACE)]

        # Add control endpoint handler.
        self.usb_control_ep = self.usb.usb.add_standard_control_endpoint(self.usb_descriptors, blacklist = blacklist) # FIXME: wrap

        # Add additional request handlers.
        for handler in self.usb_control_handlers:
            self.usb_control_ep.add_request_handler(handler)

    def add_wrapper(self):
        self.submodules.wrapper = Wrapper(self.platform)

        self.wrapper.connect_domain('sys')
        self.wrapper.connect_domain('sys2x')

    def add_platform_specific(self):
        if hasattr(self.platform, 'add_platform_specific'):
            self.platform.add_platform_specific(self)
