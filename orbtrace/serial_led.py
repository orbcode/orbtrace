from migen import *

from litex.soc.interconnect.stream import Endpoint, Pipeline, Converter, Cast, CombinatorialActor

class Output(Module):
    def __init__(self):
        self.sink = sink = Endpoint([('data', 1)])
        self.out = out = Signal()

        self.submodules.fsm = fsm = FSM()

        data = Signal()
        last = Signal()

        cnt = Signal(13)
        cnt_done = Signal()

        self.comb += cnt_done.eq(cnt == 0)
        self.sync += If(~cnt_done, cnt.eq(cnt - 1))

        time_bit_4 = round(75e6 * 0.3e-6)
        time_end = round(75e6 * 85e-6)

        fsm.act('IDLE',
            out.eq(0),
            If(sink.valid,
                NextState('HIGH'),
                NextValue(cnt, time_bit_4),
            ),
        )

        fsm.act('HIGH',
            out.eq(1),
            If(cnt_done,
                NextState('DATA'),
                NextValue(cnt, time_bit_4),

                sink.ready.eq(1),
                NextValue(data, sink.data),
                NextValue(last, sink.last),
            ),
        )

        fsm.act('DATA',
            out.eq(data),
            If(cnt_done,
                NextState('LOW'),
                NextValue(cnt, 2 * time_bit_4),
            ),
        )

        fsm.act('LOW',
            out.eq(0),
            If(cnt_done,
                If(last,
                    NextState('END'),
                    NextValue(cnt, time_end),
                ).Else(
                    NextState('HIGH'),
                    NextValue(cnt, time_bit_4),
                )
            ),
        )

        fsm.act('END',
            out.eq(0),
            If(cnt_done,
                NextState('IDLE'),
            ),
        )

class Generator(Module):
    def __init__(self, num):
        self.leds = leds = Array(Record([('r', 1), ('g', 1), ('b', 1)]) for i in range(num))

        self.source = source = Endpoint([('r', 1), ('g', 1), ('b', 1)])

        cnt = Signal(max = num)

        self.comb += [
            source.r.eq(leds[cnt].r),
            source.g.eq(leds[cnt].g),
            source.b.eq(leds[cnt].b),
            source.valid.eq(1),
            source.first.eq(cnt == 0),
            source.last.eq(cnt == num - 1),
        ]

        self.sync += If(source.ready,
            cnt.eq(cnt + 1),
            If(source.last,
                cnt.eq(0),
            ),
        )

class BrightnessController(CombinatorialActor):
    def __init__(self, brightness):
        self.sink = sink = Endpoint([('r', 1), ('g', 1), ('b', 1)])
        self.source = source = Endpoint([('r', 8), ('g', 8), ('b', 8)])

        self.comb += [
            If(sink.r, source.r.eq(brightness)),
            If(sink.g, source.g.eq(brightness)),
            If(sink.b, source.b.eq(brightness)),
        ]

        super().__init__()

class SerialLedController(Module):
    def __init__(self, pad, num):
        self.submodules.generator = Generator(num)
        self.leds = self.generator.leds

        self.submodules.brightness_controller = BrightnessController(8)

        self.submodules.cast = Cast([('b', 8), ('r', 8), ('g', 8)], [('data', 24)])

        self.submodules.converter = Converter(24, 1, reverse = True)

        self.submodules.output = Output()

        self.submodules.pipeline = Pipeline(
            self.generator,
            self.brightness_controller,
            self.cast,
            self.converter,
            self.output,
        )

        self.comb += pad.eq(self.output.out)
