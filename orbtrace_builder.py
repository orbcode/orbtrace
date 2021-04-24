#!/usr/bin/env python3

import deps

import os
import argparse

from litex.soc.integration.soc_core import soc_core_args, soc_core_argdict
from litex.soc.integration.builder import Builder, builder_args, builder_argdict
from litex.build.lattice.trellis import trellis_args, trellis_argdict

from orbtrace.soc import OrbSoC

def main():
    parser = argparse.ArgumentParser(description = "Orbtrace", add_help = False)

    parser_actions = parser.add_argument_group('Actions')
    parser_platform = parser.add_argument_group('Platform options')

    parser_platform.add_argument("--platform", choices = ['ecpix5', 'orbtrace_mini'], required = True, help = 'Select platform')

    args, _ = parser.parse_known_args()

    if args.platform == 'ecpix5':
        from orbtrace.platforms.ecpix5 import Platform
    
    elif args.platform == 'orbtrace_mini':
        from orbtrace.platforms.orbtrace_mini import Platform

    Platform.add_arguments(parser_platform)

    # Add help after selecting platform to make sure all arguments are included
    parser_actions.add_argument('-h', '--help', action = 'help', help = 'Show this message')

    parser_actions.add_argument("--build",         action="store_true", help="Build bitstream")
    parser_actions.add_argument("--load",          action="store_true", help="Load bitstream")
    parser_actions.add_argument("--flash",         action="store_true", help="Flash bitstream to SPI Flash")

    parser_platform.add_argument("--sys-clk-freq",  default=75e6,        help="System clock frequency (default: 75MHz)")

    builder_args(parser.add_argument_group('Builder options'))
    soc_core_args(parser.add_argument_group('SoC core options'))
    trellis_args(parser.add_argument_group('Trellis options'))

    args = parser.parse_args()

    platform = Platform(
        device = args.device,
        #toolchain = 'trellis',
    )

    soc = OrbSoC(
        platform = platform,
        sys_clk_freq  = int(float(args.sys_clk_freq)),
        **soc_core_argdict(args)
    )

    builder = Builder(soc, **builder_argdict(args))
    builder.build(**trellis_argdict(args), run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

    if args.flash:
        prog = soc.platform.create_programmer()
        prog.flash(None, os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

if __name__ == "__main__":
    main()
