from nmigen import *
from usb_protocol.types import USBRequestType, USBStandardRequests, USBRequestRecipient
from luna.gateware.usb.usb2.request import USBRequestHandler

class PowerUSBHandler(USBRequestHandler):
    def __init__(self, if_num):
        super().__init__()

        self.if_num = if_num

        self.vtref_en = Signal()
        self.vtref_sel = Signal()
        self.vtpwr_en = Signal()
        self.vtpwr_sel = Signal()

        self.request_done = Signal()

    def handle_set_enable(self, m):
        setup = self.interface.setup
        channel = setup.index[8:]

        ok = Signal()

        # VTREF
        with m.If((channel == 0) | (channel == 0xff)):
            m.d.usb += self.vtref_en.eq(setup.value)
            m.d.comb += ok.eq(1)

        # VTPWR
        with m.If((channel == 1) | (channel == 0xff)):
            m.d.usb += self.vtpwr_en.eq(setup.value)
            m.d.comb += ok.eq(1)

        with m.If(self.interface.status_requested):
            with m.If(ok):
                m.d.comb += self.send_zlp()
            with m.Else():
                m.d.comb += self.interface.handshakes_out.stall.eq(1),
            m.d.comb += self.request_done.eq(1)

    def handle_set_voltage(self, m):
        setup = self.interface.setup
        channel = setup.index[8:]

        ok = Signal()

        with m.Switch(channel):
            # VTREF
            with m.Case(0):
                with m.Switch(setup.value):
                    with m.Case(3300):
                        m.d.usb += self.vtref_sel.eq(0)
                        m.d.comb += ok.eq(1)

                    with m.Case(1800):
                        m.d.usb += self.vtref_sel.eq(1)
                        m.d.comb += ok.eq(1)

            # VTPWR
            with m.Case(1):
                with m.Switch(setup.value):
                    with m.Case(3300):
                        m.d.usb += self.vtpwr_sel.eq(0)
                        m.d.comb += ok.eq(1)

                    with m.Case(5000):
                        m.d.usb += self.vtpwr_sel.eq(1)
                        m.d.comb += ok.eq(1)

        with m.If(self.interface.status_requested):
            with m.If(ok):
                m.d.comb += self.send_zlp()
            with m.Else():
                m.d.comb += self.interface.handshakes_out.stall.eq(1),
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

                with m.If(setup.type == USBRequestType.VENDOR):
                    with m.Switch(setup.request):
                        with m.Case(0x01):
                            m.next = 'SET_ENABLE'
                        with m.Case(0x02):
                            m.next = 'SET_VOLTAGE'

            with m.State('SET_ENABLE'):
                self.handle_set_enable(m)
                self.transition(m)

            with m.State('SET_VOLTAGE'):
                self.handle_set_voltage(m)
                self.transition(m)

            with m.State('UNHANDLED'):
                self.handle_unhandled(m)
                self.transition(m)

        return m
