#
# This file is part of usb_protocol.
#
""" Convenience emitters for simple, standard descriptors. """

import unittest

from contextlib import contextmanager

from usb_protocol.emitters.descriptors           import emitter_for_format
from usb_protocol.emitters.descriptor import ComplexDescriptorEmitter

from  usb_protocol.types    import LanguageIDs
from  usb_protocol.types.descriptors.standard import *
from ...types.descriptors.standard import InterfaceAssociationDescriptor

# Create our basic emitters...
DeviceDescriptorEmitter         = emitter_for_format(DeviceDescriptor)
StringDescriptorEmitter         = emitter_for_format(StringDescriptor)
StringLanguageDescriptorEmitter = emitter_for_format(StringLanguageDescriptor)
DeviceQualifierDescriptor       = emitter_for_format(DeviceQualifierDescriptor)

# ... our basic superspeed emitters ...
USB2ExtensionDescriptorEmitter                  = emitter_for_format(USB2ExtensionDescriptor)
SuperSpeedUSBDeviceCapabilityDescriptorEmitter  = emitter_for_format(SuperSpeedUSBDeviceCapabilityDescriptor)
SuperSpeedEndpointCompanionDescriptorEmitter    = emitter_for_format(SuperSpeedEndpointCompanionDescriptor)

# ... convenience functions ...
def get_string_descriptor(string):
    """ Generates a string descriptor for the relevant string. """

    emitter = StringDescriptorEmitter()
    emitter.bString = string
    return emitter.emit()

# ... and complex emitters.
class InterfaceAssociationDescriptorEmitter(ComplexDescriptorEmitter):
    """ Emitter that creates an InterfaceAssociationDescriptor. """

    DESCRIPTOR_FORMAT = InterfaceAssociationDescriptor

    def _pre_emit(self):
        # Ensure that our function string is an index, if we can.
        if self._collection and hasattr(self, 'iFunction'):
            self.iFunction = self._collection.ensure_string_field_is_index(self.iFunction)

class EndpointDescriptorEmitter(ComplexDescriptorEmitter):
    """ Emitter that creates an EndpointDescriptor. """

    DESCRIPTOR_FORMAT = EndpointDescriptor

    @contextmanager
    def SuperSpeedCompanion(self):
        """ Context manager that allows addition of a SuperSpeed Companion to this endpoint descriptor.

        It can be used with a `with` statement; and yields an SuperSpeedEndpointCompanionDescriptorEmitter
        that can be populated:

            with endpoint.SuperSpeedEndpointCompanion() as d:
                d.bMaxBurst = 1

        This adds the relevant descriptor, automatically.
        """

        descriptor = SuperSpeedEndpointCompanionDescriptorEmitter()
        yield descriptor

        self.add_subordinate_descriptor(descriptor)


class InterfaceDescriptorEmitter(ComplexDescriptorEmitter):
    """ Emitter that creates an InterfaceDescriptor. """

    DESCRIPTOR_FORMAT = InterfaceDescriptor

    @contextmanager
    def EndpointDescriptor(self, *, add_default_superspeed=False):
        """ Context manager that allows addition of a subordinate endpoint descriptor.

        It can be used with a `with` statement; and yields an EndpointDesriptorEmitter
        that can be populated:

            with interface.EndpointDescriptor() as d:
                d.bEndpointAddress = 0x01
                d.bmAttributes     = 0x80
                d.wMaxPacketSize   = 64
                d.bInterval        = 0

        This adds the relevant descriptor, automatically.
        """

        descriptor = EndpointDescriptorEmitter()
        yield descriptor

        # If we're adding a default SuperSpeed extension, do so.
        if add_default_superspeed:
            with descriptor.SuperSpeedCompanion():
                pass

        self.add_subordinate_descriptor(descriptor)


    def _pre_emit(self):

        # Count our endpoints, and update our internal count.
        self.bNumEndpoints = self._type_counts[StandardDescriptorNumbers.ENDPOINT]

        # Ensure that our interface string is an index, if we can.
        if self._collection and hasattr(self, 'iInterface'):
            self.iInterface = self._collection.ensure_string_field_is_index(self.iInterface)



class ConfigurationDescriptorEmitter(ComplexDescriptorEmitter):
    """ Emitter that creates a configuration descriptor. """

    DESCRIPTOR_FORMAT = ConfigurationDescriptor

    @contextmanager
    def InterfaceDescriptor(self):
        """ Context manager that allows addition of a subordinate interface descriptor.

        It can be used with a `with` statement; and yields an InterfaceDescriptorEmitter
        that can be populated:

            with interface.InterfaceDescriptor() as d:
                d.bInterfaceNumber = 0x01
                [snip]

        This adds the relevant descriptor, automatically. Note that populating derived
        fields such as bNumEndpoints aren't necessary; they'll be populated automatically.
        """
        descriptor = InterfaceDescriptorEmitter(collection=self._collection)
        yield descriptor

        self.add_subordinate_descriptor(descriptor)


    @contextmanager
    def InterfaceAssociationDescriptor(self):
        """ Context manager that allows addition of a subordinate interface association descriptor.

        It can be used with a `with` statement; and yields an InterfaceAssociationDescriptorEmitter
        that can be populated:

            with interface.InterfaceAssociationDescriptor() as d:
                d.bFirstInterface = 0
                [snip]

        This adds the relevant descriptor, automatically.
        """
        descriptor = InterfaceAssociationDescriptorEmitter(collection=self._collection)
        yield descriptor

        self.add_subordinate_descriptor(descriptor)


    def _pre_emit(self):

        # Count our interfaces. Alternate settings of the same interface do not count multiple times.
        self.bNumInterfaces = len(set([subordinate[2] for subordinate in self._subordinates if (subordinate[1] == StandardDescriptorNumbers.INTERFACE)]))

        # Figure out our total length.
        subordinate_length = sum(len(sub) for sub in self._subordinates)
        self.wTotalLength = subordinate_length + self.DESCRIPTOR_FORMAT.sizeof()

        # Ensure that our configuration string is an index, if we can.
        if self._collection and hasattr(self, 'iConfiguration'):
            self.iConfiguration = self._collection.ensure_string_field_is_index(self.iConfiguration)



class DeviceDescriptorCollection:
    """ Object that builds a full collection of descriptors related to a given USB device. """

    # Most systems seem happiest with en_US (ugh), so default to that.
    DEFAULT_SUPPORTED_LANGUAGES = [LanguageIDs.ENGLISH_US]


    def __init__(self, automatic_language_descriptor=True):
        """
        Parameters:
            automatic_language_descriptor -- If set or not provided, a language descriptor will automatically
                                             be added if none exists.
        """


        self._automatic_language_descriptor = automatic_language_descriptor

        # Create our internal descriptor tracker.
        # Keys are a tuple of (type, index).
        self._descriptors = {}

        # Track string descriptors as they're created.
        self._next_string_index = 1
        self._index_for_string = {}


    def ensure_string_field_is_index(self, field_value):
        """ Processes the given field value; if it's not an string index, converts it to one.

        Non-index-fields are converted to indices using `get_index_for_string`, which automatically
        adds the relevant fields to our string descriptor collection.
        """

        if isinstance(field_value, str):
            return self.get_index_for_string(field_value)
        else:
            return field_value


    def get_index_for_string(self, string):
        """ Returns an string descriptor index for the given string.

        If a string descriptor already exists for the given string, its index is
        returned. Otherwise, a string descriptor is created.
        """

        # If we already have a descriptor for this string, return it.
        if string in self._index_for_string:
            return self._index_for_string[string]


        # Otherwise, create one:

        # Allocate an index...
        index = self._next_string_index
        self._index_for_string[string] = index
        self._next_string_index += 1

        # ... store our string descriptor with it ...
        identifier = StandardDescriptorNumbers.STRING, index
        self._descriptors[identifier] = get_string_descriptor(string)

        # ... and return our index.
        return index


    def add_descriptor(self, descriptor, index=0, descriptor_type=None):
        """ Adds a descriptor to our collection.

        Parameters:
            descriptor      -- The descriptor to be added.
            index           -- The index of the relevant descriptor. Defaults to 0.
            descriptor_type -- The type of the descriptor to be added. If `None`,
                               this is automatically derived from the descriptor contents.
        """

        # If this is an emitter rather than a descriptor itself, convert it.
        if hasattr(descriptor, 'emit'):
            descriptor = descriptor.emit()

        # Figure out the identifier (type + index) for this descriptor...
        if (descriptor_type is None):
            descriptor_type = descriptor[1]
        identifier = descriptor_type, index

        # ... and store it.
        self._descriptors[identifier] = descriptor


    def add_language_descriptor(self, supported_languages=None):
        """ Adds a language descriptor to the list of device descriptors.

        Parameters:
            supported_languages -- A list of languages supported by the device.
        """

        if supported_languages is None:
            supported_languages = self.DEFAULT_SUPPORTED_LANGUAGES

        descriptor = StringLanguageDescriptorEmitter()
        descriptor.wLANGID = supported_languages
        self.add_descriptor(descriptor)


    @contextmanager
    def DeviceDescriptor(self):
        """ Context manager that allows addition of a device descriptor.

        It can be used with a `with` statement; and yields an DeviceDescriptorEmitter
        that can be populated:

            with collection.DeviceDescriptor() as d:
                d.idVendor  = 0xabcd
                d.idProduct = 0x1234
                [snip]

        This adds the relevant descriptor, automatically.
        """
        descriptor = DeviceDescriptorEmitter()
        yield descriptor

        # If we have any string fields, ensure that they're indices before continuing.
        for field in ('iManufacturer', 'iProduct', 'iSerialNumber'):
            if hasattr(descriptor, field):
                value = getattr(descriptor, field)
                index = self.ensure_string_field_is_index(value)
                setattr(descriptor, field, index)

        self.add_descriptor(descriptor)


    @contextmanager
    def ConfigurationDescriptor(self):
        """ Context manager that allows addition of a configuration descriptor.

        It can be used with a `with` statement; and yields an ConfigurationDescriptorEmitter
        that can be populated:

            with collection.ConfigurationDescriptor() as d:
                d.bConfigurationValue = 1
                [snip]

        This adds the relevant descriptor, automatically. Note that populating derived
        fields such as bNumInterfaces aren't necessary; they'll be populated automatically.
        """
        descriptor = ConfigurationDescriptorEmitter(collection=self)
        yield descriptor

        self.add_descriptor(descriptor)


    @contextmanager
    def BOSDescriptor(self):
        """ Context manager that allows addition of a Binary Object Store descriptor.

        It can be used with a `with` statement; and yields an BinaryObjectStoreDescriptorEmitter
        that can be populated:

            with collection.BOSDescriptor() as d:
                [snip]

        This adds the relevant descriptor, automatically. Note that populating derived
        fields such as bNumDeviceCaps aren't necessary; they'll be populated automatically.
        """
        descriptor = BinaryObjectStoreDescriptorEmitter()
        yield descriptor

        self.add_descriptor(descriptor)


    def _ensure_has_language_descriptor(self):
        """ ensures that we have a language descriptor; adding one if necessary."""

        # if we're not automatically adding a language descriptor, we shouldn't do anything,
        # and we'll just ignore this.
        if not self._automatic_language_descriptor:
            return

        # if we don't have a language descriptor, add our default one.
        if (StandardDescriptorNumbers.STRING, 0) not in self._descriptors:
            self.add_language_descriptor()



    def get_descriptor_bytes(self, type_number: int, index: int = 0):
        """ Returns the raw, binary descriptor for a given descriptor type/index.

        Parmeters:
            type_number -- The descriptor type number.
            index       -- The index of the relevant descriptor, if relevant.
        """

        # If this is a request for a language descriptor, return one.
        if (type_number, index) == (StandardDescriptorNumbers.STRING, 0):
            self._ensure_has_language_descriptor()

        return self._descriptors[(type_number, index)]


    def __iter__(self):
        """ Allow iterating over each of our descriptors; yields (index, value, descriptor). """
        self._ensure_has_language_descriptor()
        return ((number, index, desc) for ((number, index), desc) in self._descriptors.items())




class BinaryObjectStoreDescriptorEmitter(ComplexDescriptorEmitter):
    """ Emitter that creates a BinaryObjectStore descriptor. """

    DESCRIPTOR_FORMAT = BinaryObjectStoreDescriptor

    @contextmanager
    def USB2Extension(self):
        """ Context manager that allows addition of a USB 2.0 Extension to this Binary Object Store.

        It can be used with a `with` statement; and yields an USB2ExtensionDescriptorEmitter
        that can be populated:

            with bos.USB2Extension() as e:
                e.bmAttributes = 1

        This adds the relevant descriptor, automatically.
        """

        descriptor = USB2ExtensionDescriptorEmitter()
        yield descriptor

        self.add_subordinate_descriptor(descriptor)


    @contextmanager
    def SuperSpeedUSBDeviceCapability(self):
        """ Context manager that allows addition of a SS Device Capability to this Binary Object Store.

        It can be used with a `with` statement; and yields an SuperSpeedUSBDeviceCapabilityDescriptorEmitter
        that can be populated:

            with bos.SuperSpeedUSBDeviceCapability() as e:
                e.wSpeedSupported       = 0b1110
                e.bFunctionalitySupport = 1

        This adds the relevant descriptor, automatically.
        """

        descriptor = SuperSpeedUSBDeviceCapabilityDescriptorEmitter()
        yield descriptor

        self.add_subordinate_descriptor(descriptor)


    def _pre_emit(self):

        # Figure out the total length of our descriptor, including subordinates.
        subordinate_length = sum(len(sub) for sub in self._subordinates)
        self.wTotalLength = subordinate_length + self.DESCRIPTOR_FORMAT.sizeof()

        # Count our subordinate descriptors, and update our internal count.
        self.bNumDeviceCaps = len(self._subordinates)



class SuperSpeedDeviceDescriptorCollection(DeviceDescriptorCollection):
    """ Object that builds a full collection of descriptors related to a given USB3 device. """

    def __init__(self, automatic_descriptors=True):
        """
        Parameters:
            automatic_descriptors -- If set or not provided, certian required descriptors will be
                                     be added if none exists.
        """
        self._automatic_descriptors = automatic_descriptors
        super().__init__(automatic_language_descriptor=automatic_descriptors)


    def add_default_bos_descriptor(self):
        """ Adds a default, empty BOS descriptor. """

        # Create an empty BOS descriptor...
        descriptor = BinaryObjectStoreDescriptorEmitter()

        # ... populate our default required descriptors...
        descriptor.add_subordinate_descriptor(USB2ExtensionDescriptorEmitter())
        descriptor.add_subordinate_descriptor(SuperSpeedUSBDeviceCapabilityDescriptorEmitter())

        # ... and add it to our overall BOS descriptor.
        self.add_descriptor(descriptor)


    def _ensure_has_bos_descriptor(self):
        """ Ensures that we have a BOS descriptor; adding one if necessary."""

        # If we're not automatically adding a language descriptor, we shouldn't do anything,
        # and we'll just ignore this.
        if not self._automatic_descriptors:
            return

        # If we don't have a language descriptor, add our default one.
        if (StandardDescriptorNumbers.BOS, 0) not in self._descriptors:
            self.add_default_bos_descriptor()


    def __iter__(self):
        """ Allow iterating over each of our descriptors; yields (index, value, descriptor). """
        self._ensure_has_bos_descriptor()
        return super().__iter__()


class EmitterTests(unittest.TestCase):

    def test_string_emitter(self):
        emitter = StringDescriptorEmitter()
        emitter.bString = "Hello"

        self.assertEqual(emitter.emit(), b"\x0C\x03H\0e\0l\0l\0o\0")


    def test_string_emitter_function(self):
        self.assertEqual(get_string_descriptor("Hello"), b"\x0C\x03H\0e\0l\0l\0o\0")


    def test_configuration_emitter(self):
        descriptor = bytes([

            # config descriptor
            12,     # length
            2,      # type
            25, 00, # total length
            1,      # num interfaces
            1,      # configuration number
            0,      # config string
            0x80,   # attributes
            250,    # max power

            # interface descriptor
            9,    # length
            4,    # type
            0,    # number
            0,    # alternate
            1,    # num endpoints
            0xff, # class
            0xff, # subclass
            0xff, # protocol
            0,    # string

            # endpoint descriptor
            7,       # length
            5,       # type
            0x01,    # address
            2,       # attributes
            64, 0,   # max packet size
            255,     # interval
        ])


        # Create a trivial configuration descriptor...
        emitter = ConfigurationDescriptorEmitter()

        with emitter.InterfaceDescriptor() as interface:
            interface.bInterfaceNumber = 0

            with interface.EndpointDescriptor() as endpoint:
                endpoint.bEndpointAddress = 1


        # ... and validate that it maches our reference descriptor.
        binary = emitter.emit()
        self.assertEqual(len(binary), len(descriptor))


    def test_descriptor_collection(self):
        collection = DeviceDescriptorCollection()

        with collection.DeviceDescriptor() as d:
            d.idVendor           = 0xdead
            d.idProduct          = 0xbeef
            d.bNumConfigurations = 1

            d.iManufacturer      = "Test Company"
            d.iProduct           = "Test Product"


        with collection.ConfigurationDescriptor() as c:
            c.bConfigurationValue = 1

            with c.InterfaceDescriptor() as i:
                i.bInterfaceNumber = 1

                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = 0x81

                with i.EndpointDescriptor() as e:
                    e.bEndpointAddress = 0x01


        results = list(collection)

        # We should wind up with four descriptor entries, as our endpoint/interface descriptors are
        # included in our configuration descriptor.
        self.assertEqual(len(results), 5)

        # Supported languages string.
        self.assertIn((3, 0, b'\x04\x03\x09\x04'), results)

        # Manufacturer / product string.
        self.assertIn((3, 1, b'\x1a\x03T\x00e\x00s\x00t\x00 \x00C\x00o\x00m\x00p\x00a\x00n\x00y\x00'), results)
        self.assertIn((3, 2, b'\x1a\x03T\x00e\x00s\x00t\x00 \x00P\x00r\x00o\x00d\x00u\x00c\x00t\x00'), results)

        # Device descriptor.
        self.assertIn((1, 0, b'\x12\x01\x00\x02\x00\x00\x00@\xad\xde\xef\xbe\x00\x00\x01\x02\x00\x01'), results)

        # Configuration descriptor, with subordinates.
        self.assertIn((2, 0, b'\t\x02 \x00\x01\x01\x00\x80\xfa\t\x04\x01\x00\x02\xff\xff\xff\x00\x07\x05\x81\x02@\x00\xff\x07\x05\x01\x02@\x00\xff'), results)


    def test_empty_descriptor_collection(self):
        collection = DeviceDescriptorCollection(automatic_language_descriptor=False)
        results = list(collection)
        self.assertEqual(len(results), 0)

    def test_automatic_language_descriptor(self):
        collection = DeviceDescriptorCollection(automatic_language_descriptor=True)
        results = list(collection)
        self.assertEqual(len(results), 1)

if __name__ == "__main__":
    unittest.main()
