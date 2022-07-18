#!/usr/bin/env python3

import sys
import argparse
import usb1

def parse_power(value):
    if value in ['off', 'on']:
        return value

    return float(value)

input_formats = {
    'off': 0x00,
    '1': 0x01,
    '2': 0x02,
    '4': 0x03,
    'manchester': 0x10,
    'manchester_tpiu': 0x11,
    'nrz': 0x12,
    'nrz_tpiu': 0x13,
}

parser = argparse.ArgumentParser()

parser_discovery = parser.add_argument_group('Device discovery')
parser_discovery.add_argument('--vid', type = lambda x: int(x, 16), default = 0x1209, help = 'Select VID')
parser_discovery.add_argument('--pid', type = lambda x: int(x, 16), default = 0x3443, help = 'Select PID')
parser_discovery.add_argument('--serial', help = 'Select serial number')

parser_actions = parser.add_argument_group('Actions')
parser_actions.add_argument('--input-format', choices = input_formats, help = 'Set trace input format')
parser_actions.add_argument('--vtref', type = parse_power, help = 'Set VTREF')
parser_actions.add_argument('--vtpwr', type = parse_power, help = 'Set VTPWR')

parser_options = parser.add_argument_group('Options')
parser_options.add_argument('--proxy', action = 'store_true', help = 'Use proxy interface')

args = parser.parse_args()

class Orbtrace:
    def __init__(self, device):
        self.trace_if = None
        self.power_if = None
        self.proxy_if = None

        self.read_config(device)

        self.handle = device.open()

    def read_config(self, device):
        config, = device.iterConfigurations()

        for interface in config.iterInterfaces():
            setting, *_ = interface.iterSettings()

            if setting.getClass() != 0xff:
                continue
            
            if setting.getSubClass() == ord('T'):
                self.trace_if = setting.getNumber()

            if setting.getSubClass() == ord('P'):
                self.power_if = setting.getNumber()

            if setting.getSubClass() == ord('X'):
                self.proxy_if = setting.getNumber()
    
    def trace_set_input_format(self, format, use_proxy = False):
        if_num = self.proxy_if if use_proxy else self.trace_if
        assert if_num is not None

        self.handle.controlWrite(0x41, 0x01, input_formats[format], if_num, b'')

    def power_set_enable(self, channel, enable):
        assert self.power_if is not None

        self.handle.controlWrite(0x41, 0x01, enable, (channel << 8) | self.power_if, b'')

    def power_set_voltage(self, channel, voltage):
        assert self.power_if is not None

        print(channel, voltage)

        self.handle.controlWrite(0x41, 0x02, voltage, (channel << 8) | self.power_if, b'')

with usb1.USBContext() as context:
    devices = []

    for device in context.getDeviceIterator():
        if device.getVendorID() != args.vid:
            continue

        if device.getProductID() != args.pid:
            continue

        if args.serial and device.getSerialNumber() != args.serial:
            continue

        devices.append(device)

    if not devices:
        print('Found no orbtrace devices.', file = sys.stderr)
        sys.exit(1)

    if len(devices) > 1:
        print('Found multiple orbtrace devices:', file = sys.stderr)
        for device in devices:
            print(device.getSerialNumber(), file = sys.stderr)
        print('Please select one with --serial.', file = sys.stderr)
        sys.exit(1)

    orbtrace = Orbtrace(devices[0])

    if args.input_format:
        orbtrace.trace_set_input_format(args.input_format, args.proxy)

    if args.vtref:
        if args.vtref in ['off', 'on']:
            orbtrace.power_set_enable(0, args.vtref == 'on')
        else:
            orbtrace.power_set_voltage(0, int(args.vtref * 1000))
            orbtrace.power_set_enable(0, 1)

    if args.vtpwr:
        if args.vtpwr in ['off', 'on']:
            orbtrace.power_set_enable(1, args.vtpwr == 'on')
        else:
            orbtrace.power_set_voltage(1, int(args.vtpwr * 1000))
            orbtrace.power_set_enable(1, 1)
