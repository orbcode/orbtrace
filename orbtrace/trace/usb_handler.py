from nmigen import *
from usb_protocol.types import USBRequestType, USBStandardRequests, USBRequestRecipient
from luna.gateware.usb.usb2.request import USBRequestHandler

class TraceUSBHandler(USBRequestHandler):
    def __init__(self, if_num):
        super().__init__()

        self.if_num = if_num

        self.width = Signal(2, reset = 3)

        self.request_done = Signal()

    def handle_set_interface(self, m):
        # TODO: Select trace output format based on self.interface.setup.value.

        with m.If(self.interface.status_requested):
            m.d.comb += self.send_zlp()
            m.d.comb += self.request_done.eq(1)

    def handle_set_trace_type(self, m):
        m.d.usb += self.width.eq(self.interface.setup.value)

        with m.If(self.interface.status_requested):
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

        targeting_if = (setup.recipient == USBRequestRecipient.INTERFACE) & (setup.index[:8] == self.if_num)

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

                with m.If(setup.type == USBRequestType.STANDARD):
                    with m.Switch(setup.request):
                        with m.Case(USBStandardRequests.SET_INTERFACE):
                            m.next = 'SET_INTERFACE'

                with m.If(setup.type == USBRequestType.VENDOR):
                    with m.Switch(setup.request):
                        with m.Case(0x01):
                            m.next = 'SET_TRACE_TYPE'
            
            with m.State('SET_INTERFACE'):
                self.handle_set_interface(m)
                self.transition(m)
            
            with m.State('SET_TRACE_TYPE'):
                self.handle_set_trace_type(m)
                self.transition(m)
            
            with m.State('UNHANDLED'):
                self.handle_unhandled(m)
                self.transition(m)

        return m
