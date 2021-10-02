#!/usr/bin/env python3

import sys
import argparse
import usb1

def parse_power(value):
    if value in ['off', 'on']:
        return value

    return float(value)

parser = argparse.ArgumentParser()

parser_discovery = parser.add_argument_group('Device discovery')
parser_discovery.add_argument('--vid', type = lambda x: int(x, 16), default = 0x1209, help = 'Select VID')
parser_discovery.add_argument('--pid', type = lambda x: int(x, 16), default = 0x3443, help = 'Select PID')
parser_discovery.add_argument('--serial', help = 'Select serial number')

parser_actions = parser.add_argument_group('Actions')
parser_actions.add_argument('--width', type = int, choices = [1, 2, 4], help = 'Set trace width')
parser_actions.add_argument('--vtref', type = parse_power, help = 'Set VTREF')
parser_actions.add_argument('--vtpwr', type = parse_power, help = 'Set VTPWR')

args = parser.parse_args()

class Orbtrace:
    def __init__(self, device):
        self.trace_if = None
        self.power_if = None

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
    
    def trace_set_width(self, width):
        assert self.trace_if is not None

        type = {1: 1, 2: 2, 4: 3}[width]

        self.handle.controlWrite(0x41, 0x01, type, self.trace_if, b'')

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

    if args.width:
        orbtrace.trace_set_width(args.width)

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
