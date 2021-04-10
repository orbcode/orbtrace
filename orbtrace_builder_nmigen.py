#!/usr/bin/env python3
#

import deps

import os
import itertools

from nmigen                  import *
from nmigen.build            import ResourceError
from nmigen.hdl              import ClockSignal

from nmigen.build.dsl        import Pins
from nmigen.hdl.xfrm         import DomainRenamer, ClockDomain
from usb_protocol.emitters   import DeviceDescriptorCollection


from luna.usb2               import USBDevice, USBMultibyteStreamInEndpoint, USBStreamInEndpoint, USBStreamOutEndpoint
from luna.gateware.stream.arbiter import StreamArbiter, StreamMultiplexer, StreamInterface
from usb_protocol.types      import USBTransferType

from orbtrace.nmigen.orbtrace_platform_ecp5  import orbtrace_ECPIX5_85_Platform
from orbtrace.nmigen.traceIF                 import TRACE_TO_USB

from orbtrace.nmigen.cmsis_dap               import CMSIS_DAP

# USB Endpoint configuration

# Interface 0
CMSIS_DAPV1_IF                    = 0
CMSIS_DAPV1_NAME                  = "CMSIS-DAPv1"
CMSIS_DAPV1_IN_ENDPOINT_NUMBER    = 1
CMSIS_DAPV1_IN_ENDPOINT_SIZE      = 64
CMSIS_DAPV1_OUT_ENDPOINT_NUMBER   = 1
CMSIS_DAPV1_OUT_ENDPOINT_SIZE     = 64

# Interface 1
CMSIS_DAPV2_IF                    = 1
CMSIS_DAPV2_NAME                  = "CMSIS-DAPv2"
CMSIS_DAPV2_IN_ENDPOINT_NUMBER    = 2
CMSIS_DAPV2_OUT_ENDPOINT_NUMBER   = 2
CMSIS_DAPV2_ENDPOINT_SIZE         = 512

# Interface 2
DEBUG_IF                          = 2
DEBUG_IF_NAME                     = "DEBUG"
DEBUG_ENDPOINT_NUMBER             = 3
DEBUG_ENDPOINT_SIZE               = 512

# Interface 3
TRACE_IF                          = 3
TRACE_IF_NAME                     = "TRACE"
TRACE_ENDPOINT_NUMBER             = 4
TRACE_ENDPOINT_SIZE               = 512

# Interface 4

# Length of various bit indicators
RX_LED_STRETCH_BITS   = 26
TX_LED_STRETCH_BITS   = 16
OVF_LED_STRETCH_BITS  = 26
HB_BITS               = 27

class StreamMux(Elaboratable):
    def __init__(self, s1, s2, domain="sync", direction="in"):
        self.s1 = s1
        self.s2 = s2
        self._domain = domain
        self._dir = direction
        self.selB = Signal()
        self.sout = StreamInterface()

    def elaborate(self, platform):
        m = Module()

        if (self._dir=="in"):
            with m.If(self.selB):
                m.d.comb += self.sout.attach(self.s2)
            with m.Else():
                m.d.comb += self.sout.attach(self.s1)
        else:
            with m.If(self.selB):
                m.d.comb += self.s2.attach(self.sout)
            with m.Else():
                m.d.comb += self.s1.attach(self.sout)

        m = DomainRenamer(self._domain)(m)
        return m


class OrbtraceDevice(Elaboratable):

    def create_descriptors(self):
        descriptors = DeviceDescriptorCollection()

        # We'll need a device descriptor...
        with descriptors.DeviceDescriptor() as d:
            d.idVendor           = 0x1209
            d.idProduct          = 0x3443  # Allocated from pid.codes

            d.iManufacturer      = "Orbcode"
            d.iProduct           = "Orbtrace with CMSIS-DAP"
            d.iSerialNumber      = "Unserialed"

            d.bNumConfigurations = 1

        # ... and a description of the USB configuration we'll provide.
        with descriptors.ConfigurationDescriptor() as c:
            with c.InterfaceDescriptor() as i:
                i._collection = descriptors
                i.bInterfaceNumber = CMSIS_DAPV1_IF
                i.iInterface = CMSIS_DAPV1_NAME

                i.bInterfaceClass = 3
                i.bInterfaceSubclass = 0
                i.bInterfaceProtocol = 0

                # This is the HID descriptor
                i.add_subordinate_descriptor(b"\x09\x21\x11\x01\x00\x01\x22\x21\x00")
                descriptors.add_descriptor(b"\x06\x00\xFF\x09\x01\xA1\x01\x15\x00\x26\xFF\x00\x75\x08\x95\x40\x09\x01\x81"
                                             b"\x02\x95\x40\x09\x01\x91\x02\x95\x01\x09\x01\xB1\x02\xC0",descriptor_type=0x22)

                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = 0x80 | CMSIS_DAPV1_IN_ENDPOINT_NUMBER
                    e.wMaxPacketSize   = CMSIS_DAPV1_IN_ENDPOINT_SIZE
                    e.bmAttributes     = USBTransferType.INTERRUPT
                    e.bInterval        = 2

                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = CMSIS_DAPV1_OUT_ENDPOINT_NUMBER
                    e.wMaxPacketSize   = CMSIS_DAPV1_OUT_ENDPOINT_SIZE
                    e.bmAttributes     = USBTransferType.INTERRUPT
                    e.bInterval        = 2

            with c.InterfaceDescriptor() as i:
                i._collection = descriptors
                i.bInterfaceNumber = CMSIS_DAPV2_IF
                i.iInterface = CMSIS_DAPV2_NAME
                i.bInterfaceClass = 0xff
                i.bInterfaceSubclass = 0
                i.bInterfaceProtocol = 0

                # CMSIS-DAPv2 endpoints need to be in a specific order...
                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = CMSIS_DAPV2_OUT_ENDPOINT_NUMBER
                    e.wMaxPacketSize   = CMSIS_DAPV2_ENDPOINT_SIZE

                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = 0x80 | CMSIS_DAPV2_IN_ENDPOINT_NUMBER
                    e.wMaxPacketSize   = CMSIS_DAPV2_ENDPOINT_SIZE

            with c.InterfaceDescriptor() as i:
                i._collection = descriptors
                i.bInterfaceNumber = DEBUG_IF
                i.iInterface = DEBUG_IF_NAME
                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = 0x80 | DEBUG_ENDPOINT_NUMBER
                    e.wMaxPacketSize   = DEBUG_ENDPOINT_SIZE

            with c.InterfaceDescriptor() as i:
                i._collection = descriptors
                i.bInterfaceNumber = TRACE_IF
                i.iInterface = TRACE_IF_NAME
                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = 0x80 | TRACE_ENDPOINT_NUMBER
                    e.wMaxPacketSize   = TRACE_ENDPOINT_SIZE

        return descriptors

    def elaborate(self, platform):
        self.rx_stretch  = Signal(RX_LED_STRETCH_BITS)
        self.tx_stretch  = Signal(TX_LED_STRETCH_BITS)
        self.ovf_stretch = Signal(OVF_LED_STRETCH_BITS)
        self.hb          = Signal(HB_BITS)
        self.isV2        = Signal()

        # Individual LED conditions to be signalled
        self.hb_ind   = Signal()
        self.dat_ind  = Signal()
        self.ovf_ind  = Signal()
        self.tx_ind   = Signal()
        self.inv_ind  = Signal()
        self.leds_out = Signal(8)

        m = Module()

        # State of things to be reported via the USB link
        m.d.comb += self.leds_out.eq(Cat( self.dat_ind, self.tx_ind, C(0,3), self.ovf_ind, self.inv_ind, self.hb_ind ))

        def get_all_resources(name):
            resources = []
            for number in itertools.count():
                try:
                    resources.append(platform.request(name, number))
                except ResourceError:
                    break
            return resources

        # Generate our domain clocks/resets.
        m.submodules.car = platform.clock_domain_generator()

        # Create our USB device interface...
        ulpi = platform.request(platform.default_usb_connection)
        m.submodules.usb = usb = USBDevice(bus=ulpi)

        # Add our standard control endpoint to the device.
        descriptors = self.create_descriptors()
        usb.add_standard_control_endpoint(descriptors)

        # Add CMSIS_DAP endpoints
        # =======================
        cmsisdapV1In = USBStreamInEndpoint(
            endpoint_number=CMSIS_DAPV1_IN_ENDPOINT_NUMBER,
            max_packet_size=CMSIS_DAPV1_IN_ENDPOINT_SIZE
        )
        usb.add_endpoint(cmsisdapV1In)

        cmsisdapV1Out = USBStreamOutEndpoint(
            endpoint_number=CMSIS_DAPV1_OUT_ENDPOINT_NUMBER,
            max_packet_size=CMSIS_DAPV1_OUT_ENDPOINT_SIZE
        )
        usb.add_endpoint(cmsisdapV1Out)

        cmsisdapV2In = USBStreamInEndpoint(
            endpoint_number=CMSIS_DAPV2_IN_ENDPOINT_NUMBER,
            max_packet_size=CMSIS_DAPV2_ENDPOINT_SIZE
        )
        usb.add_endpoint(cmsisdapV2In)

        cmsisdapV2Out = USBStreamOutEndpoint(
            endpoint_number=CMSIS_DAPV2_OUT_ENDPOINT_NUMBER,
            max_packet_size=CMSIS_DAPV2_ENDPOINT_SIZE
        )
        usb.add_endpoint(cmsisdapV2Out)

        # Add DEBUG endpoint
        # ==================
        debug_ep = USBMultibyteStreamInEndpoint(
            endpoint_number=DEBUG_ENDPOINT_NUMBER,
            max_packet_size=DEBUG_ENDPOINT_SIZE,
            byte_width=16
        )
        usb.add_endpoint(debug_ep)

        # Add TRACE endpoint
        # ==================
        trace_ep = USBMultibyteStreamInEndpoint(
            endpoint_number=TRACE_ENDPOINT_NUMBER,
            max_packet_size=TRACE_ENDPOINT_SIZE,
            byte_width=16
        )
        usb.add_endpoint(trace_ep)

        # Create a tracing instance
        tracepins=platform.request("tracein",0,xdr={"dat":2})
        m.submodules.trace = trace = TRACE_TO_USB(tracepins, trace_ep, self.leds_out)

        # Merge the cmsis-dap streams into one
        m.submodules.cmsisdapIn_mux = cmisdapIn_muxstream = StreamMux(cmsisdapV1In.stream,cmsisdapV2In.stream,domain="usb" )
        m.submodules.cmsisdapOut_mux = cmisdapOut_muxstream = StreamMux(cmsisdapV1Out.stream,cmsisdapV2Out.stream,domain="usb", direction="out" )
        m.d.comb += [
            cmisdapIn_muxstream.selB.eq(self.isV2),
            cmisdapOut_muxstream.selB.eq(self.isV2)
            ]

        # Switch between v2 and v1 interfaces ... hopefully this only happens at the start of a conversation
        with m.If(cmsisdapV1Out.stream.valid):
            m.d.usb += self.isV2.eq(0)
        with m.If(cmsisdapV2Out.stream.valid):
            m.d.usb += self.isV2.eq(1)

        dbgpins = platform.request("dbgif",0)

        # Create the CMSIS DAP instance
        m.submodules.cmsisdap = cmsisdap = CMSIS_DAP( cmisdapIn_muxstream.sout, cmisdapOut_muxstream.sout, dbgpins, self.isV2 )

        # Connect our device as a high speed device by default.
        m.d.comb += [
            usb.connect          .eq(1),
            usb.full_speed_only  .eq(0),
        ]

        # Run LED indicators - Heartbeat
        m.d.usb += self.hb.eq(self.hb-1)

        # Overflow
        with m.If((trace.overflow_ind) | (self.ovf_stretch!=0)):
            m.d.usb += self.ovf_stretch.eq(self.ovf_stretch-1)

        # Receive
        with m.If(trace.rx_ind):
            m.d.usb += self.rx_stretch.eq(~0)
        with m.Elif(self.rx_stretch!=0):
            m.d.usb += self.rx_stretch.eq(self.rx_stretch-1)

        # Transmit
        with m.If(trace.tx_ind):
            m.d.usb += self.tx_stretch.eq(~0)
        with m.Elif(self.tx_stretch!=0):
            m.d.usb += self.tx_stretch.eq(self.tx_stretch-1)

        # Map indicators to Actual LEDs; Rightmost to leftmost
        rgbled = [res for res in get_all_resources("rgb_led")]

        m.d.comb += [
            self.hb_ind.eq(self.hb[HB_BITS-1]==0),
            self.dat_ind.eq(self.rx_stretch!=0),
            self.tx_ind.eq(self.tx_stretch!=0),
            self.ovf_ind.eq(self.ovf_stretch!=0) ]

        m.d.comb += [ rgbled[0].r.o.eq(0),              rgbled[0].g.o.eq(self.hb_ind),                   rgbled[0].b.o.eq(0)            ]
        m.d.comb += [ rgbled[1].r.o.eq(self.ovf_ind),   rgbled[1].g.o.eq(self.tx_ind & ~self.ovf_ind),   rgbled[1].b.o.eq(0)            ]
        m.d.comb += [ rgbled[2].r.o.eq(trace.inv_ind),  rgbled[2].g.o.eq(0),                             rgbled[2].b.o.eq(0)            ]
        m.d.comb += [ rgbled[3].r.o.eq(0),              rgbled[3].g.o.eq(0),                             rgbled[3].b.o.eq(self.dat_ind) ]

        return m

if __name__ == "__main__":
    platform = orbtrace_ECPIX5_85_Platform()
    with open('verilog/traceIF.v') as f:
        platform.add_file("traceIF.v",f)
    with open('verilog/swdIF.v') as f:
        platform.add_file("swdIF.v",f)
    with open('verilog/dbgIF.v') as f:
        platform.add_file("dbgIF.v",f)
    platform.build(OrbtraceDevice(), build_dir='build', do_program=True)
