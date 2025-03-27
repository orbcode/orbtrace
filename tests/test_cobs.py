from sim_helpers import *

from amaranth.sim import Simulator, SimulatorContext

from orbtrace.trace.cobs import COBSEncoder
from cobs.cobs import encode

def test_cobs():
    packets = [
        [0],
        [0, 0],
        [0, 1, 0],
        [1],
        [1, 1],
        [1, 0, 1],
        [i & 0xff for i in range(0, 255)],
        [i & 0xff for i in range(1, 255)],
        [i & 0xff for i in range(1, 256)],
        [i & 0xff for i in range(2, 257)],
        [i & 0xff for i in range(3, 258)],
    ]

    dut = COBSEncoder()

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    @sim.add_testbench
    async def input_testbench(ctx: SimulatorContext):
        await ctx.tick()

        for packet in packets:
            await send_packet(ctx, dut.input, packet)

    @sim.add_testbench
    async def output_testbench(ctx: SimulatorContext):
        for packet in packets:
            encoded = await recv_packet(ctx, dut.output)
            assert encoded == list(encode(bytes(packet)))

    @sim.add_process
    async def timeout(ctx: SimulatorContext):
        await ctx.tick().repeat(10_000)
        raise TimeoutError('Simulation timed out')

    sim.run()
