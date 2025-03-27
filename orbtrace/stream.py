from amaranth import *
from amaranth.lib import stream, data, wiring, fifo

class Packet(data.StructLayout):
    def __init__(self, element_shape = 8, *, has_first = False, has_last = False):
        assert has_first or has_last
        layout = {'data': element_shape}
        if has_first:
            layout['first'] = 1
        if has_last:
            layout['last'] = 1
        super().__init__(layout)

        self.has_first = has_first
        self.has_last = has_last

class SyncFIFOBuffered(wiring.Component):
    def __init__(self, shape, depth):
        super().__init__({
            'input': wiring.In(stream.Signature(shape)),
            'output': wiring.Out(stream.Signature(shape)),
        })
        self.width = Shape.cast(shape).width
        self.depth = depth

    def elaborate(self, platform):
        m = Module()
        m.submodules.fifo = _fifo = fifo.SyncFIFOBuffered(width = self.width, depth = self.depth)

        m.d.comb += [
            # Input
            self.input.ready.eq(_fifo.w_rdy),
            _fifo.w_en.eq(self.input.valid),
            _fifo.w_data.eq(self.input.payload),

            # Output
            self.output.valid.eq(_fifo.r_rdy),
            self.output.payload.eq(_fifo.r_data),
            _fifo.r_en.eq(self.output.ready),
        ]

        return m

class AsyncFIFOBuffered(wiring.Component):
    def __init__(self, shape, depth):
        super().__init__({
            'input': wiring.In(stream.Signature(shape)),
            'output': wiring.Out(stream.Signature(shape)),
        })
        self.width = Shape.cast(shape).width
        self.depth = depth

    def elaborate(self, platform):
        m = Module()
        m.submodules.fifo = _fifo = fifo.AsyncFIFOBuffered(width = self.width, depth = self.depth)

        m.d.comb += [
            # Input
            self.input.ready.eq(_fifo.w_rdy),
            _fifo.w_en.eq(self.input.valid),
            _fifo.w_data.eq(self.input.payload),

            # Output
            self.output.valid.eq(_fifo.r_rdy),
            self.output.payload.eq(_fifo.r_data),
            _fifo.r_en.eq(self.output.ready),
        ]

        return m

class Serializer(wiring.Component):
    def __init__(self, shape: data.ArrayLayout):
        assert isinstance(shape, data.ArrayLayout)

        super().__init__({
            'input': wiring.In(stream.Signature(shape)),
            'output': wiring.Out(stream.Signature(shape.elem_shape)),
        })

        self.shape = shape

    def elaborate(self, platform):
        m = Module()

        idx = Signal(range(self.shape.length))

        m.d.comb += [
            self.input.ready.eq(self.output.ready & (idx == self.shape.length - 1)),
            self.output.valid.eq(self.input.valid),
            self.output.payload.eq(self.input.payload[idx]),
        ]

        with m.If(self.output.valid & self.output.ready):
            m.d.sync += idx.eq(idx + 1)

            with m.If(idx == self.shape.length - 1):
                m.d.sync += idx.eq(0)

        return m
