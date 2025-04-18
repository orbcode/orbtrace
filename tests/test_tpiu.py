from sim_helpers import *

import itertools

from amaranth.sim import Simulator, SimulatorContext

from orbtrace.trace import tpiu

def test_packetizer():
    dut = tpiu.Packetizer(timeout = 2000)

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    @sim.add_testbench
    async def input_testbench(ctx: SimulatorContext):
        await ctx.tick()

        for i in range(1024 + 512):
            await stream_put(ctx, dut.input, {'channel': 1, 'data': i & 0xff})
    
    @sim.add_testbench
    async def output_testbench(ctx: SimulatorContext):
        assert await recv_packet(ctx, dut.output) == [1, *((i & 0xff) for i in range(1024))]
        assert await recv_packet(ctx, dut.output) == [1, *((i & 0xff) for i in range(512))]

    @sim.add_process
    async def timeout(ctx: SimulatorContext):
        await ctx.tick().repeat(10_000)
        raise TimeoutError('Simulation timed out')

    sim.run()

def test_packetizer_slow_timeout():
    dut = tpiu.Packetizer(timeout = 1000)

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    @sim.add_process
    async def input_testbench(ctx: SimulatorContext):
        await ctx.tick()

        for i in itertools.count():
            await stream_put(ctx, dut.input, {'channel': 1, 'data': i & 0xff})
            await ctx.tick().repeat(100)

    @sim.add_testbench
    async def output_testbench(ctx: SimulatorContext):
        assert await recv_packet(ctx, dut.output) == [1, *((i & 0xff) for i in range(10))]
        assert await recv_packet(ctx, dut.output) == [1, *((i & 0xff) for i in range(10, 20))]

    @sim.add_process
    async def timeout(ctx: SimulatorContext):
        await ctx.tick().repeat(10_000)
        raise TimeoutError('Simulation timed out')

    sim.run()

def test_demux():
    dut = tpiu.TPIUDemux(timeout = 1000)

    sim = Simulator(dut)
    sim.add_clock(1e-6)

    @sim.add_testbench
    async def input_testbench(ctx: SimulatorContext):
        await ctx.tick()

        payloads = [
            # ITM hello world without padding.
            bytes.fromhex('03 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 01 48 01 64 88'),
            bytes.fromhex('00 6c 00 6c 00 6f 00 20 00 77 00 6f 00 72 00 ff'),
            bytes.fromhex('6c 01 64 01 20 01 0a 0b 00 00 00 00 0a 00 00 44'),
            bytes.fromhex('00 00 0a 00 00 00 00 0b 00 00 00 00 0a 00 00 42'),
            bytes.fromhex('00 00 0a 00 00 00 00 0b 00 00 00 00 0a 00 00 42'),
            bytes.fromhex('03 00 00 0b 00 00 00 00 0a 00 00 00 00 0b 00 10'),
            bytes.fromhex('00 00 00 0b 00 00 00 00 0a 00 00 00 00 0b 00 10'),
            bytes.fromhex('00 00 00 0b 00 00 00 00 0a 00 00 00 00 0b 00 10'),
            bytes.fromhex('00 00 00 0b 00 00 00 00 0a 00 00 00 00 0b 00 10'),
            bytes.fromhex('00 00 00 0b 00 00 00 00 0a 00 00 00 00 0b 00 10'),
            bytes.fromhex('00 00 00 0b 00 00 00 00 0a 00 00 00 00 0b 00 10'),
            bytes.fromhex('00 00 00 0b 00 00 00 00 0a 00 00 00 00 0b 00 10'),
            bytes.fromhex('00 00 00 0b 00 00 00 00 0a 00 00 00 00 0b 00 10'),

            # ITM hello world with padding.
            bytes.fromhex('03 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 01 01 48 00 48'),
            bytes.fromhex('03 01 01 65 03 01 01 6c 03 01 01 6c 03 01 6e aa'),
            bytes.fromhex('03 01 01 20 03 01 01 77 03 01 01 6f 03 01 72 2a'),
            bytes.fromhex('03 01 01 6c 03 01 01 64 03 01 01 21 03 01 0a 2a'),
            bytes.fromhex('03 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
            bytes.fromhex('00 0b 00 00 00 00 0a 00 00 00 00 0b 00 00 00 08'),
        ]

        for payload in payloads:
            await stream_put(ctx, dut.input, payload)

    @sim.add_testbench
    async def output_testbench(ctx: SimulatorContext):
        res = await recv_packet(ctx, dut.output)
        assert bytes(res) == bytes.fromhex('''
            01 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b
            00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00
            00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00
            0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00
            00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00
            00 01 48 01 65 01 6c 01 6c 01 6f 01 20 01 77 01 6f 01 72 01 6c 01 64 01 21 01 0a 0b 00 00 00 00
            0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00
            00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00
            00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b
            00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00
            00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 0b 00 00 00 00 0b 00 00
            00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00
            0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00
            00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00
            00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b
            00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 01 48 01 65 01 6c 01 6c
            01 6f 01 20 01 77 01 6f 01 72 01 6c 01 64 01 21 01 0a 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00
            00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b
            00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00
            00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00
            0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00 00 00 00 0b 00
            00 00 00 0b 00 00 00
        ''')

    @sim.add_process
    async def timeout(ctx: SimulatorContext):
        await ctx.tick().repeat(10_000)
        raise TimeoutError('Simulation timed out')

    sim.run()
