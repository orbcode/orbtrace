from amaranth import *
from usb_protocol.types import USBRequestType, USBStandardRequests, USBRequestRecipient

from luna.gateware.usb.usb2.request import USBRequestHandler
from luna.gateware.usb.stream import USBInStreamInterface
from luna.gateware.stream.generator import StreamSerializer
from luna.gateware.memory import TransactionalizedFIFO

class DFUHandler(USBRequestHandler):
    def __init__(self, if_num, areas):
        super().__init__()

        self.source = Record([
            ('data', 8),
            ('addr', 24),
            ('valid', 1),
            ('ready', 1),
            ('first', 1),
            ('last', 1),
        ])

        self.if_num = if_num

        self.addr = Signal(24)

        self.areas = Array(areas)
        self.area_sel = Signal(range(len(self.areas)))

        self.new_request = Signal()
        self.request_done = Signal()
        self.state = Signal(8, reset = 2)

    def handle_set_interface(self, m):
        m.d.usb += self.area_sel.eq(self.interface.setup.value)

        with m.If(self.interface.status_requested):
            m.d.comb += self.send_zlp()
            m.d.comb += self.request_done.eq(1)

    def handle_get_status(self, m):
        m.d.comb += [
            self.transmitter.stream.attach(self.interface.tx),
            Cat(self.transmitter.data).eq(Cat(
                C(0, 8),
                C(0, 24),
                self.state,
                C(0, 8),
            )),
            self.transmitter.start.eq(self.interface.data_requested),
        ]

        with m.If(self.interface.status_requested):
            m.d.comb += self.interface.handshakes_out.ack.eq(1)
            m.d.comb += self.request_done.eq(1)

    def handle_dnload(self, m):
        m.submodules.fifo = fifo = TransactionalizedFIFO(width = 8, depth = 256, domain = 'usb')

        interface = self.interface
        rx = self.interface.rx

        last_addr = Signal(24)

        m.d.comb += [
            fifo.write_data.eq(rx.payload),
            fifo.write_en.eq(rx.next & rx.valid),

            fifo.write_discard.eq(interface.rx_invalid),
            fifo.write_commit.eq(interface.rx_ready_for_response),

            self.source.data.eq(fifo.read_data),
            self.source.valid.eq(~fifo.empty),
            fifo.read_en.eq(self.source.ready),
            fifo.read_commit.eq(1),

            self.source.addr.eq(self.addr),
            self.source.last.eq(self.addr == last_addr),
        ]

        with m.If(self.source.valid & self.source.ready):
            m.d.usb += self.addr.eq(self.addr + 1)

        with m.If(self.new_request):
            with m.If(self.interface.setup.length > 0):
                m.d.usb += self.state.eq(5)
            with m.Else():
                m.d.usb += self.state.eq(2)
            
            m.d.usb += last_addr.eq(self.addr + self.interface.setup.length - 1)

            # Starting a new DNLOAD cycle?
            with m.If(self.state == 2):
                m.d.usb += [
                    self.addr.eq(self.areas[self.area_sel]),
                    self.source.first.eq(1),
                ]

        with m.If(self.interface.rx_ready_for_response):
            m.d.comb += self.interface.handshakes_out.ack.eq(1)

        with m.If(self.interface.status_requested):
            with m.If(fifo.empty):
                m.d.comb += self.send_zlp()
                m.d.comb += self.request_done.eq(1)
            
            with m.Else():
                m.d.comb += self.interface.handshakes_out.nak.eq(1)

        #m.d.comb += self.source.ready.eq(1)
    
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

        m.d.usb += self.new_request.eq(0)

        with m.FSM(domain = 'usb'):
            with m.State('IDLE'):
                self.transition(m)

            with m.State('DISPATCH'):
                m.d.usb += self.new_request.eq(1)

                m.next = 'UNHANDLED'

                with m.If(setup.type == USBRequestType.STANDARD):
                    with m.Switch(setup.request):
                        with m.Case(USBStandardRequests.SET_INTERFACE):
                            m.next = 'SET_INTERFACE'

                with m.If(setup.type == USBRequestType.CLASS):
                    with m.Switch(setup.request):
                        #with m.Case(0): # DFU_DETACH
                        with m.Case(1): # DFU_DNLOAD
                            m.next = 'DFU_DNLOAD'
                        #with m.Case(2): # DFU_UPLOAD
                        with m.Case(3): # DFU_GETSTATUS
                            m.next = 'DFU_GETSTATUS'

                        #with m.Case(4): # DFU_CLRSTATUS
                        #with m.Case(5): # DFU_GETSTATE
                        #with m.Case(6): # DFU_ABORT
            
            with m.State('SET_INTERFACE'):
                self.handle_set_interface(m)
                self.transition(m)

            with m.State('DFU_DNLOAD'):
                self.handle_dnload(m)
                self.transition(m)

            with m.State('DFU_GETSTATUS'):
                self.handle_get_status(m)
                self.transition(m)
            
            with m.State('UNHANDLED'):
                self.handle_unhandled(m)
                self.transition(m)

        return m
