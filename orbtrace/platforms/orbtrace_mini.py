from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.openfpgaloader import OpenFPGALoader

from ..crg_ecp5 import CRG

from ..serial_led import SerialLedController

# IOs ----------------------------------------------------------------------------------------------

_io = [
    # Clk / Rst
    ('clk30', 0, Pins('L16'), IOStandard('LVCMOS33')),

    # Leds
    ('serial_led', 0, Pins('N12'), IOStandard('LVCMOS33')),

    # TODO:
    # programn
    # btn
    # power

    # Debug # FIXME: this is incomplete
    ('debug', 0,
        Subsignal('jtck',     Pins('B13')),
        Subsignal('jtms',     Pins('A14')),
        Subsignal('jtms_dir', Pins('A15')),
        Subsignal('jtdo',     Pins('B12')),
        Subsignal('jtdi',     Pins('A12')),
        IOStandard('LVCMOS33')
    ),

    # Trace
    ('trace', 0,
        Subsignal('clk',  Pins('C8')),
        Subsignal('data', Pins('A10 B9 A9 B8')),
        IOStandard('LVCMOS33')
    ),

    # HyperRAM
    ('hyperram', 0,
        Subsignal('rst',  Pins('M16')),
        Subsignal('cs_n', Pins('M15')),
        Subsignal('clk',  Pins('N16')),
        Subsignal('rwds', Pins('R12')),
        Subsignal('dq',   Pins('T15 P13 T14 R13 T13 R14 R15 P14')),
        IOStandard('LVCMOS33')
    ),

    # SPIFlash
    ('spiflash', 0,
        Subsignal('cs_n', Pins('N8')),
        Subsignal('mosi', Pins('T8')),
        Subsignal('miso', Pins('T7')),
        Subsignal('wp',   Pins('M7')),
        Subsignal('hold', Pins('N7')),
        IOStandard('LVCMOS33')
    ),
    ('spiflash4x', 0,
        Subsignal('cs_n', Pins('N8')),
        Subsignal('dq', Pins('T8', 'T7', 'M7', 'N7')),
        IOStandard('LVCMOS33')
    ),

    # USB
    ('ulpi', 0,
        Subsignal('rst_n',  Pins('T4')),
        Subsignal('clk_o',  Pins('R5')),
        Subsignal('dir',  Pins('T3')),
        Subsignal('nxt',  Pins('R3')),
        Subsignal('stp',  Pins('R4')),
        Subsignal('data', Pins('T2 R2 R1 P2 P1 N1 M2 M1')),
        IOStandard('LVCMOS33')
    ),

    # I2C
    ('i2c', 0,
        Subsignal('scl', Pins('L2')),
        Subsignal('sda', Pins('L1')),
        IOStandard('LVCMOS33')
    ),
]

# Connectors ---------------------------------------------------------------------------------------

_connectors = [
    ('ext',
        '- - - - - - - - - - - - - - - - - - '
        'J5 K1 J4 K2 - - '
        'K3 J1 J3 J2 - - '
        'H4 H2 H5 G1 - - '
        'G3 G2 H3 F1 - - '
        'G4 F2 G5 E1 - - '
        'F3 E2 E3 D1 - - '
        'F4 C1 F5 C2 - - '
        'D3 B1 C3 B2 - - '
        '- - - - '
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(LatticePlatform):
    default_clk_name   = 'clk30'
    default_clk_period = 1e9/30e6

    def __init__(self, device='25F', toolchain='trellis', **kwargs):
        assert device in ['25F', '45F']
        LatticePlatform.__init__(self, f'LFE5U-{device}-8BG256C', _io, _connectors, toolchain=toolchain, **kwargs)

    def get_crg(self, sys_clk_freq):
        crg = CRG(self, sys_clk_freq)
        crg.add_usb()
        return crg

    def add_leds(self, soc):
        soc.submodules.serial_led = SerialLedController(self.request('serial_led'), 5)

        soc.led_status = soc.serial_led.leds[0]
        soc.led_debug  = soc.serial_led.leds[1]
        soc.led_trace  = soc.serial_led.leds[2]
        soc.led_vtref  = soc.serial_led.leds[3]
        soc.led_vtpwr  = soc.serial_led.leds[4]

    def create_programmer(self):
        return OpenFPGALoader('ecpix5')

    def do_finalize(self, fragment):
        LatticePlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request('clk30', loose=True), 1e9/30e6)
        #self.add_period_constraint(self.lookup_request('ulpi:clk', 0, loose=True), 1e9/60e6)
        self.add_period_constraint(self.lookup_request('trace:clk', 0, loose=True), 1e9/120e6)

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('--device', choices = ['25F', '45F'], default = '25F', help = 'ECP5 device (default: 25F)')