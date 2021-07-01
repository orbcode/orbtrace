from migen import *
from litex.build.generic_platform import Subsignal, Pins, IOStandard
from litex_boards.platforms import lambdaconcept_ecpix5

from ..crg_ecp5 import CRG

from ..serial_led import SerialLedController

from litespi.opcodes import SpiNorFlashOpCodes as Codes
from ..flash_modules import IS25LP256D

class Platform(lambdaconcept_ecpix5.Platform):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.add_extension([
            ('debug', 0,
                Subsignal('jtck', Pins('pmod6:1')),
                Subsignal('jtms', Pins('pmod6:7')),
                Subsignal('jtms_dir', Pins('pmod6:3')),
                Subsignal('jtdo', Pins('pmod7:3')),
                Subsignal('jtdi', Pins('pmod6:6')),

                Subsignal('nrst_i', Pins('pmod7:7')),
                Subsignal('nrst_o_n', Pins('pmod6:4')),
            ),
            ('trace', 0,
                Subsignal('clk', Pins('pmod7:2')),
                Subsignal('data', Pins('pmod7:6 pmod7:1 pmod7:5 pmod7:4')),
            ),
            ('target_power', 0,
                Subsignal('vtref_en_n', Pins('pmod6:2')),
                Subsignal('vtpwr_en_n', Pins('pmod6:5')),
            ),
            ('gpio', 0,
                Subsignal('data', Pins('pmod4:0')),
            ),
            ('serial_led', 0, Pins('pmod5:0')),
        ])

    def get_crg(self, sys_clk_freq):
        return CRG(self, sys_clk_freq)

    def get_flash_module(self):
        return IS25LP256D(Codes.READ_1_4_4)

    def add_leds(self, soc):
        soc.submodules.serial_led = SerialLedController(self.request('serial_led'), 5)

        soc.led_status = soc.serial_led.leds[0]
        soc.led_debug  = soc.serial_led.leds[1]
        soc.led_trace  = soc.serial_led.leds[2]

        #soc.led_status = Record([('r', 1), ('g', 1), ('b', 1)])
        #soc.led_debug  = Record([('r', 1), ('g', 1), ('b', 1)])
        #soc.led_trace  = Record([('r', 1), ('g', 1), ('b', 1)])

        off = Record([('r', 1), ('g', 1), ('b', 1)])

        led_map = [
            (soc.led_status, self.request('rgb_led', 0)),
            (soc.led_debug,  self.request('rgb_led', 1)),
            (soc.led_trace,  self.request('rgb_led', 2)),
            (off,            self.request('rgb_led', 3)),
        ]

        for led, pads in led_map:
            soc.comb += [
                pads.r.eq(~led.r),
                pads.g.eq(~led.g),
                pads.b.eq(~led.b),
            ]

    def do_finalize(self, fragment):
        lambdaconcept_ecpix5.Platform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("ulpi:clk", 0, loose=True), 1e9/60e6)
        self.add_period_constraint(self.lookup_request("trace:clk", 0, loose=True), 1e9/120e6)

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('--device', choices = ['45F', '85F'], default = '85F', help = 'ECP5 device (default: 85F)')