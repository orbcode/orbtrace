from sim_helpers import *

from amaranth.sim import Simulator, SimulatorContext

from orbtrace.trace import swo

def test_pulse_length_capture():
    dut = swo.PulseLengthCapture()

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    @sim.add_testbench
    async def input_testbench(ctx: SimulatorContext):
        await ctx.tick()

        levels = [
            3, 3, 3, 3, 3, 0, 0, 0, # 10 high, 6 low
            3, 3, 3, 3, 3, 3, 3, 0, # 14 high, 2 low
            3, 3, 1, 0, 0, 0, 0, 0, # 5 high, 11 low
            3, 3, 2, 3, 0, 1, 0, 0, # 8 high, 8 low (with glitches)
            3, 3, 0, 0, 2, 3, 1, 0, # 4 high, 5 low, 4 high, 3 low
            3,
        ]

        for level in levels:
            ctx.set(dut.input, level)
            await ctx.tick()

    @sim.add_testbench
    async def output_testbench(ctx: SimulatorContext):
        await stream_get(ctx, dut.output)

        counts = [
            10, 6,
            14, 2,
            5, 11,
            8, 8,
            4, 5, 4, 3,
        ]

        for i, n in enumerate(counts):
            res = await stream_get(ctx, dut.output)
            assert res['level'] != i % 2
            assert res['count'] == n

        res = await stream_get(ctx, dut.output)
        assert res['level'] == 1
        assert res['count'] == 0x8000

        res = await stream_get(ctx, dut.output)
        assert res['level'] == 1
        assert res['count'] == 0x8000

    @sim.add_process
    async def timeout(ctx: SimulatorContext):
        await ctx.tick().repeat(100_000)
        raise TimeoutError('Simulation timed out')

    sim.run()

def test_manchester_decoder():
    dut = swo.ManchesterDecoder()

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    @sim.add_testbench
    async def input_testbench(ctx: SimulatorContext):
        await ctx.tick()

        payloads = [
            {'level': 1, 'count': 10},
            {'level': 0, 'count': 20},
            {'level': 1, 'count': 20},
            {'level': 0, 'count': 10},
            {'level': 1, 'count': 10},
            {'level': 0, 'count': 20},
            {'level': 1, 'count': 10},
            {'level': 0, 'count': 10},
            {'level': 1, 'count': 20},
            {'level': 0, 'count': 20},
            {'level': 1, 'count': 20},
            {'level': 0, 'count': 40},
        ]

        for payload in payloads:
            await stream_put(ctx, dut.input, payload)

    @sim.add_testbench
    async def output_testbench(ctx: SimulatorContext):
        expected = [0, 1, 1, 0, 0, 1, 0, 1]
        for i, e in enumerate(expected):
            res = await stream_get(ctx, dut.output)
            assert res['data'] == e
            assert res['first'] == (i == 0)

    @sim.add_process
    async def timeout(ctx: SimulatorContext):
        await ctx.tick().repeat(100_000)
        raise TimeoutError('Simulation timed out')

    sim.run()
