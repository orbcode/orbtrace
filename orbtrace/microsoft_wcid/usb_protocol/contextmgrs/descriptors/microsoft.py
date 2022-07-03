#
# This file is part of usb-protocol.
#
from usb_protocol.emitters.descriptor import ComplexDescriptorEmitter

from usb_protocol.emitters.descriptors.standard import BinaryObjectStoreDescriptorEmitter
from ...emitters.descriptors.microsoft import PlatformDescriptorEmitter, PlatformDescriptorCollection

class DescriptorContextManager:
    ParentDescriptor = ComplexDescriptorEmitter
    DescriptorEmitter = None

    def __init__(self, parentDesc : ParentDescriptor):
        self._parent = parentDesc
        self._descriptor = self.DescriptorEmitter()

    def __enter__(self):
        return self._descriptor

    def __exit__(self, exc_type, exc_value, traceback):
        # If an exception was raised, fast exit
        if not (exc_type is None and exc_value is None and traceback is None):
            return
        self._parent.add_subordinate_descriptor(self._descriptor)

class PlatformDescriptor(DescriptorContextManager):
    ParentDescriptor = BinaryObjectStoreDescriptorEmitter
    DescriptorEmitter = lambda self: PlatformDescriptorEmitter(platform_collection = self._platform_collection)

    def __init__(self, parentDesc : ParentDescriptor, platform_collection : PlatformDescriptorCollection):
        self._platform_collection = platform_collection
        super().__init__(parentDesc)