from amaranth import *
from usb_protocol.types import USBRequestType, USBStandardRequests, USBRequestRecipient
from luna.gateware.usb.usb2.request import USBRequestHandler

class TraceUSBHandler(USBRequestHandler):
    def __init__(self, if_num, proxy_if_num):
        super().__init__()

        self.if_num = if_num
        self.proxy_if_num = proxy_if_num

        self.input_format = Signal(8)
        self.async_baudrate = Signal(32)
        self.async_baudrate_strobe = Signal()

        self.idx = Signal(16)

        self.request_done = Signal()

    def handle_set_interface(self, m):
        # TODO: Select trace output format based on self.interface.setup.value.

        with m.If(self.interface.status_requested):
            m.d.comb += self.send_zlp()
            m.d.comb += self.request_done.eq(1)

    def handle_set_input_format(self, m):
        m.d.usb += self.input_format.eq(self.interface.setup.value)

        with m.If(self.interface.status_requested):
            m.d.comb += self.send_zlp()
            m.d.comb += self.request_done.eq(1)

    def handle_set_async_baudrate(self, m):
        rx = self.interface.rx

        with m.If(rx.next & rx.valid):
            m.d.usb += self.idx.eq(self.idx + 1)

            with m.Switch(self.idx):
                with m.Case(0):
                    m.d.usb += self.async_baudrate[0:8].eq(rx.payload)
                with m.Case(1):
                    m.d.usb += self.async_baudrate[8:16].eq(rx.payload)
                with m.Case(2):
                    m.d.usb += self.async_baudrate[16:24].eq(rx.payload)
                with m.Case(3):
                    m.d.usb += self.async_baudrate[24:32].eq(rx.payload)

        with m.If(self.interface.rx_ready_for_response):
            m.d.comb += self.interface.handshakes_out.ack.eq(1)

        with m.If(self.interface.status_requested):
            m.d.comb += self.async_baudrate_strobe.eq(1)
            m.d.comb += self.send_zlp()
            m.d.comb += self.request_done.eq(1)

    def handle_unhandled(self, m):
        interface = self.interface

        with m.If(interface.rx_ready_for_response | interface.data_requested | interface.status_requested):
            m.d.comb += [
                interface.handshakes_out.stall.eq(1),
                self.request_done.eq(1),
            ]

    def transition(self, m):
        setup = self.interface.setup

        with m.If(self.request_done):
            m.next = 'IDLE'

        targeting_if = (setup.recipient == USBRequestRecipient.INTERFACE) & ((setup.index[:8] == self.if_num) | (setup.index[:8] == self.proxy_if_num))

        with m.If(setup.received & targeting_if):
            m.next = 'DISPATCH'

    def elaborate(self, platform):
        m = Module()

        setup = self.interface.setup

        with m.FSM(domain = 'usb'):
            with m.State('IDLE'):
                self.transition(m)

            with m.State('DISPATCH'):
                m.next = 'UNHANDLED'

                m.d.usb += self.idx.eq(0)

                with m.If(setup.type == USBRequestType.STANDARD):
                    with m.Switch(setup.request):
                        with m.Case(USBStandardRequests.SET_INTERFACE):
                            m.next = 'SET_INTERFACE'

                with m.If(setup.type == USBRequestType.VENDOR):
                    with m.Switch(setup.request):
                        with m.Case(0x01):
                            m.next = 'SET_INPUT_FORMAT'

                with m.If(setup.type == USBRequestType.VENDOR):
                    with m.Switch(setup.request):
                        with m.Case(0x02):
                            m.next = 'SET_ASYNC_BAUDRATE'
            
            with m.State('SET_INTERFACE'):
                self.handle_set_interface(m)
                self.transition(m)
            
            with m.State('SET_INPUT_FORMAT'):
                self.handle_set_input_format(m)
                self.transition(m)
            
            with m.State('SET_ASYNC_BAUDRATE'):
                self.handle_set_async_baudrate(m)
                self.transition(m)
            
            with m.State('UNHANDLED'):
                self.handle_unhandled(m)
                self.transition(m)

        return m
