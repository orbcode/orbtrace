#
# This file is part of usb-protocol.
#
"""
Structures describing standard USB descriptors. Versions that support parsing incomplete binary data
are available as `DescriptorType`.Partial, e.g. `DeviceDescriptor.Partial`, and are collectively available
in the `usb_protocol.types.descriptors.partial.standard` module (which, like the structs in this module,
can also be imported without `.standard`).
"""

import unittest
from enum import IntEnum

import construct
from   construct  import this

from usb_protocol.types.descriptor import DescriptorNumber, DescriptorFormat
from ..descriptor import \
    DescriptorField


class StandardDescriptorNumbers(IntEnum):
    """ Numbers of our standard descriptors. """

    DEVICE                                        =  1
    CONFIGURATION                                 =  2
    STRING                                        =  3
    INTERFACE                                     =  4
    ENDPOINT                                      =  5
    DEVICE_QUALIFIER                              =  6
    OTHER_SPEED_DESCRIPTOR                        =  7
    OTHER_SPEED                                   =  7
    INTERFACE_POWER                               =  8
    OTG                                           =  9
    DEBUG                                         = 10
    INTERFACE_ASSOCIATION                         = 11

    # SuperSpeed only
    BOS                                           = 15
    DEVICE_CAPABILITY                             = 16
    SUPERSPEED_USB_ENDPOINT_COMPANION             = 48
    SUPERSPEEDPLUS_ISOCHRONOUS_ENDPOINT_COMPANION = 49



InterfaceAssociationDescriptor = DescriptorFormat(
    "bLength"             / construct.Const(8, construct.Int8ul),
    "bDescriptorType"     / DescriptorNumber(StandardDescriptorNumbers.INTERFACE_ASSOCIATION),
    "bFirstInterface"     / DescriptorField(description="Interface number of the first interface that is associated with this function.", default=0),
    "bInterfaceCount"     / DescriptorField(description="Number of contiguous interfaces that are associated with this function"),
    "bFunctionClass"      / DescriptorField(description="Function class code"),
    "bFunctionSubclass"   / DescriptorField(description="Function subclass code"),
    "bFunctionProtocol"   / DescriptorField(description="Function protocol code"),
    "iFunction"           / DescriptorField(description="Index of a string descriptor that describes this interface", default=0),
)
