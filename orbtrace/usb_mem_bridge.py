from amaranth import Elaboratable, Module, Cat, Array, Signal
from usb_protocol.types import USBRequestType

from luna.gateware.usb.usb2.request import USBRequestHandler
from luna.gateware.usb.stream import USBInStreamInterface
from luna.gateware.stream.generator import StreamSerializer

class MemRequestHandler(USBRequestHandler):
    def __init__(self, axi_lite):
        super().__init__()

        self.axi_lite = axi_lite

    def handle_write(self, m, address):
        aw = self.axi_lite.aw
        w = self.axi_lite.w
        b = self.axi_lite.b

        m.d.comb += [
            w.strb.eq(0b1111),
            b.ready.eq(1),
        ]

        data = Array(Signal(8) for i in range(3))
        idx = Signal(range(4))

        with m.FSM(domain = 'usb') as fsm:

            with m.State('IDLE'):
                with m.If(self.interface.setup.received):
                    m.d.usb += aw.addr.eq(address)
                    m.d.usb += idx.eq(0)
                    m.next = 'ADDR'

            with m.State('ADDR'):
                m.d.comb += aw.valid.eq(1)

                with m.If(aw.ready):
                    m.next = 'RECEIVE'

            with m.State('RECEIVE'):
                with m.If(self.interface.rx.valid & self.interface.rx.next):
                    with m.If(idx < 3):
                        m.d.usb += [
                            data[idx].eq(self.interface.rx.payload),
                            idx.eq(idx + 1),
                        ]

                    with m.Else():
                        m.d.usb += w.data.eq(Cat(data, self.interface.rx.payload))
                        m.next = 'WRITE'

            with m.State('WRITE'):
                m.d.comb += w.valid.eq(1)

                with m.If(w.ready):
                    m.next = 'IDLE'

        with m.If(self.interface.rx_ready_for_response):
            m.d.comb += self.interface.handshakes_out.ack.eq(1)

        with m.If(self.interface.status_requested):
            m.d.comb += self.send_zlp()
    
    def handle_read(self, m, address):
        ar = self.axi_lite.ar
        r = self.axi_lite.r

        m.d.comb += [
            self.transmitter.stream.attach(self.interface.tx),
        ]

        with m.FSM(domain = 'usb') as fsm:
            
            with m.State('IDLE'):
                with m.If(self.interface.setup.received):
                    m.d.usb += ar.addr.eq(address)
                    m.next = 'ADDR'

            with m.State('ADDR'):
                m.d.comb += ar.valid.eq(1)

                with m.If(ar.ready):
                    m.next = 'READ'

            with m.State('READ'):
                m.d.comb += r.ready.eq(1)
                m.d.comb += self.interface.handshakes_out.nak.eq(self.interface.data_requested)

                with m.If(r.valid):
                    m.d.usb += Cat(self.transmitter.data).eq(r.data)
                    m.next = 'TRANSMIT'
            
            with m.State('TRANSMIT'):
                with m.If(self.interface.data_requested):
                    m.d.comb += self.transmitter.start.eq(1)
                    m.next = 'IDLE'

        with m.If(self.interface.status_requested):
            m.d.comb += self.interface.handshakes_out.ack.eq(1)

    def elaborate(self, platform):
        m = Module()

        m.submodules.transmitter = self.transmitter = StreamSerializer(data_length = 4, domain = 'usb', stream_type=USBInStreamInterface)

        interface         = self.interface
        setup             = self.interface.setup

        with m.If((setup.type == USBRequestType.VENDOR) & (setup.recipient == 3) & (setup.request == 0)):

            address = Cat(setup.value, setup.index)


            with m.If(setup.is_in_request):
                self.handle_read(m, address)
            
            with m.Else():
                self.handle_write(m, address)

        return m