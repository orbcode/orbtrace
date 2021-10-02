#!/usr/bin/env python3

import sys
import argparse
import usb1

parser = argparse.ArgumentParser()

parser_discovery = parser.add_argument_group('Device discovery')
parser_discovery.add_argument('--vid', type = lambda x: int(x, 16), default = 0x1209, help = 'Select VID')
parser_discovery.add_argument('--pid', type = lambda x: int(x, 16), default = 0x3443, help = 'Select PID')
parser_discovery.add_argument('--serial', help = 'Select serial number')

parser_actions = parser.add_argument_group('Actions')
parser_actions.add_argument('--width', type = int, choices = [1, 2, 4], help = 'Set trace width')

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
    
    def set_trace_width(self, width):
        assert self.trace_if is not None

        type = {1: 1, 2: 2, 4: 3}[width]

        self.handle.controlWrite(0x41, 0x01, type, self.trace_if, b'')

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
        orbtrace.set_trace_width(args.width)
