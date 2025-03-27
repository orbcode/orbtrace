from sim_helpers import *

from amaranth.lib import data
from amaranth.sim import Simulator, SimulatorContext

from orbtrace.stream import *

def test_serializer():
    dut = Serializer(data.ArrayLayout(8, 3))

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    @sim.add_testbench
    async def input_testbench(ctx: SimulatorContext):
        await ctx.tick()

        payloads = [
            (1, 2, 3),
            (4, 5, 6),
        ]

        for payload in payloads:
            await stream_put(ctx, dut.input, payload)

    @sim.add_testbench
    async def output_testbench(ctx: SimulatorContext):
        for expected in [1, 2, 3, 4, 5, 6]:
            assert await stream_get(ctx, dut.output) == expected

    @sim.add_process
    async def timeout(ctx: SimulatorContext):
        await ctx.tick().repeat(10_000)
        raise TimeoutError('Simulation timed out')

    sim.run()
