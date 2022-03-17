from amaranth import *
from usb_protocol.types import USBStandardRequests, USBRequestType, USBRequestRecipient, DescriptorTypes

from luna.gateware.usb.usb2.request import USBRequestHandler

class USBSerialNumberHandler(USBRequestHandler):
    def __init__(self, idx, bits):
        super().__init__()

        assert bits % 4 == 0

        self.idx = idx

        self.serial = Signal(bits)
        self.valid = Signal()

        self.data_length = 2 + bits // 4 * 2

        self.request_done = Signal()

    def handle_get_descriptor(self, m, max_length):
        nibble_map = Array(b'0123456789ABCDEF')

        pos = Signal(range(0, self.data_length))
        data = Signal(8)

        nibble_sel = (self.data_length - 1 - pos) >> 1
        nibble = self.serial.word_select(nibble_sel, 4)

        with m.If(pos == 0):
            m.d.comb += data.eq(self.data_length)

        with m.Elif(pos == 1):
            m.d.comb += data.eq(3)

        with m.Elif(pos[0] == 0):
            m.d.comb += data.eq(nibble_map[nibble])

        stream = self.interface.tx

        first = pos == 0
        last = (pos == self.data_length - 1) | (pos == max_length - 1)

        m.d.comb += [
            stream.first.eq(first & stream.valid),
            stream.last.eq(last & stream.valid),
        ]

        with m.FSM(domain = 'usb') as fsm:
            with m.State('IDLE'):
                m.d.usb += pos.eq(0)

                with m.If(self.interface.data_requested):
                    m.next = 'STREAMING'

            with m.State('STREAMING'):
                m.d.comb += [
                    stream.valid.eq(1),
                    stream.payload.eq(data),
                ]

                with m.If(stream.ready):
                    with m.If(last):
                        m.next = 'IDLE'

                    with m.Else():
                        m.d.usb += pos.eq(pos + 1)

        with m.If(self.interface.status_requested):
            m.d.comb += self.interface.handshakes_out.ack.eq(1)
            m.d.comb += self.request_done.eq(1)

    def elaborate(self, platform):
        m = Module()

        setup = self.interface.setup

        with m.FSM(domain = 'usb'):
            with m.State('IDLE'):
                get_descriptor = \
                    (setup.type == USBRequestType.STANDARD) & \
                    (setup.recipient == USBRequestRecipient.DEVICE) & \
                    (setup.request == USBStandardRequests.GET_DESCRIPTOR) & \
                    (setup.value == (DescriptorTypes.STRING << 8) | self.idx)

                with m.If(setup.received & get_descriptor):
                    m.next = 'GET_DESCRIPTOR'

            with m.State('GET_DESCRIPTOR'):
                self.handle_get_descriptor(m, setup.length)

                with m.If(self.request_done):
                    m.next = 'IDLE'

        return m

