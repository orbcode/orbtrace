from amaranth import *
from usb_protocol.types import USBRequestType, USBRequestRecipient

from luna.gateware.usb.usb2.request import USBRequestHandler
from luna.gateware.usb.stream import USBInStreamInterface
from luna.gateware.stream.generator import StreamSerializer

class ACMRequestHandler(USBRequestHandler):
    def __init__(self, if_num):
        super().__init__()

        self.if_num = if_num

        self.new_request = Signal()
        self.request_done = Signal()

    def handle_set_line_coding(self, m):
        with m.If(self.interface.rx_ready_for_response):
            m.d.comb += self.interface.handshakes_out.ack.eq(1)

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

        targeting_if = (setup.recipient == USBRequestRecipient.INTERFACE) & (setup.index == self.if_num)

        with m.If(setup.received & targeting_if):
            m.next = 'DISPATCH'

    def elaborate(self, platform):
        m = Module()

        m.submodules.transmitter = self.transmitter = StreamSerializer(data_length = 6, domain = 'usb', stream_type=USBInStreamInterface)

        interface         = self.interface
        setup             = self.interface.setup

        m.d.comb += interface.claim.eq((setup.recipient == USBRequestRecipient.INTERFACE) & (setup.index == self.if_num))
        m.d.usb += self.new_request.eq(0)

        with m.FSM(domain = 'usb'):
            with m.State('IDLE'):
                self.transition(m)

            with m.State('DISPATCH'):
                m.d.usb += self.new_request.eq(1)

                m.next = 'UNHANDLED'

                with m.If(setup.type == USBRequestType.CLASS):
                    with m.Switch(setup.request):
                        with m.Case(0x20): # SET_LINE_CODING
                            m.next = 'SET_LINE_CODING'
            
            with m.State('SET_LINE_CODING'):
                self.handle_set_line_coding(m)
                self.transition(m)

            with m.State('UNHANDLED'):
                self.handle_unhandled(m)
                self.transition(m)

        return m
