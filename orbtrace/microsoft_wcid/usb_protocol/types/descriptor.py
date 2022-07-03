#
# This file is part of usb-protocol.
#
""" Type elements for defining USB descriptors. """

import unittest
import construct

import usb_protocol
from usb_protocol.types.descriptor import BCDFieldAdapter

class DescriptorField(usb_protocol.types.descriptor.DescriptorField):
    """
    Construct field definition that automatically adds fields of the proper
    size to Descriptor definitions.
    """

    #
    # The C++-wonk operator overloading is Construct, not me, I swear.
    #

    # FIXME: these are really primitive views of these types;
    # we should extend these to get implicit parsing wherever possible
    USB_TYPES = {
        'b'   : construct.Int8ul,
        'bcd' : BCDFieldAdapter(construct.Int16ul),  # TODO: Create a BCD parser for this
        'i'   : construct.Int8ul,
        'id'  : construct.Int16ul,
        'bm'  : construct.Int8ul,
        'w'   : construct.Int16ul,
        'dw'  : construct.Int32ul,
    }

