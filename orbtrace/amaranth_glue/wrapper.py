import amaranth
from amaranth.hdl import _ast, _ir
from amaranth.back import verilog

import migen

from pathlib import Path

class Wrapper(migen.Module):
    def __init__(self, platform, name = 'amaranth_wrapper'):
        self.platform = platform
        self.name = name

        self.m = amaranth.Module()

        self.connections = []

    def connect(self, migen_sig, amaranth_sig):
        self.connections.append((migen_sig, amaranth_sig))

    def connect_domain(self, name):
        n = 'sync' if name == 'sys' else name

        setattr(self.m.domains, n, amaranth.ClockDomain(n))

        self.connect(migen.ClockSignal(name), amaranth.ClockSignal(n))
        self.connect(migen.ResetSignal(name), amaranth.ResetSignal(n))

    def from_amaranth(self, amaranth_sig):
        shape = amaranth_sig.shape()
        migen_sig = migen.Signal((shape.width, shape.signed), name = amaranth_sig.name)

        self.connect(migen_sig, amaranth_sig)

        return migen_sig

    def from_migen(self, migen_sig):
        amaranth_sig = amaranth.Signal(amaranth.Shape(migen_sig.nbits, migen_sig.signed))

        self.connect(migen_sig, amaranth_sig)

        return amaranth_sig

    def get_instance(self):
        connections = {}

        for m, n in self.connections:
            name, direction = self.amaranth_name_map[n]
            s = f'{direction}_{name}'

            assert s not in connections, f'Signal {s} connected multiple times.'

            connections[s] = m

        return migen.Instance(self.name, **connections)

    def generate_verilog(self):
        ports = [n for m, n in self.connections]

        fragment = _ir.Fragment.get(self.m, None).prepare(ports = ports, hierarchy = (self.name,))

        v, _name_map = verilog.convert_fragment(fragment, name = self.name)
        netlist = _ir.build_netlist(fragment, name = self.name)

        self.amaranth_name_map = _ast.SignalDict((sig, (name, 'o' if name in netlist.top.ports_o else 'i')) for name, sig, _ in fragment.ports)

        for name, domain in fragment.fragment.domains.items():
            if domain.clk in self.amaranth_name_map:
                self.amaranth_name_map[amaranth.ClockSignal(name)] = self.amaranth_name_map[domain.clk]
            if domain.rst in self.amaranth_name_map:
                self.amaranth_name_map[amaranth.ResetSignal(name)] = self.amaranth_name_map[domain.rst]

        return v

    def do_finalize(self):
        verilog_filename = str(Path(self.platform.output_dir) / 'gateware' / f'{self.name}.v')

        with open(verilog_filename, 'w') as f:
            f.write(self.generate_verilog())

        self.platform.add_source(verilog_filename)

        self.specials += self.get_instance()
