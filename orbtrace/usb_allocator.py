import uuid

from .microsoft_wcid import PlatformDescriptorCollection, PlatformDescriptor, WindowsRequestHandler

DEVICE_INTERFACE_GUID_BASE = uuid.UUID('{1c451fbb-0000-426f-bef2-93a89eb65cba}')

class USBAllocator:
    def __init__(self):
        self._next_interface = 0
        self._next_in_ep     = 1
        self._next_out_ep    = 1
        self.winusb_interfaces = []
        self.device_interface_guids = {}

    def interface(self, with_winusb=True, guid=None, guid_discriminator=None):
        n = self._next_interface
        self._next_interface += 1

        if guid is not None and guid_discriminator is not None:
            raise RuntimeError('Specify either guid or guid_discriminator, not both.')

        if guid_discriminator is not None:
            assert guid_discriminator <= 0xFFFF

            fields = list(DEVICE_INTERFACE_GUID_BASE.fields)
            fields[1] = guid_discriminator
            guid = str(uuid.UUID(fields=fields))

        if guid is not None:
            if not with_winusb:
                raise RuntimeError('guid and guid_discriminator is Windows-specific. There is no reason to apply to non-WinUSB interfaces')

            guid = uuid.UUID(guid)

            if guid in self.device_interface_guids.values():
                raise RuntimeError(f'Duplicated GUID: {guid}')

            self.device_interface_guids[n] = guid

        if with_winusb:
            if guid is None:
                raise RuntimeError('Specify guid or guid_discriminator for WinUSB-capable interfaces.')

            self.winusb_interfaces.append(n)

        return n

    def in_ep(self):
        n = self._next_in_ep
        self._next_in_ep += 1
        return n

    def out_ep(self):
        n = self._next_out_ep
        self._next_out_ep += 1
        return n

    def create_microsoft_os_2_0_descriptors(self, usb_descriptors, usb_control_handlers):
        platformDescriptors = PlatformDescriptorCollection()
        with usb_descriptors.BOSDescriptor() as bos:
            with PlatformDescriptor(bos, platform_collection = platformDescriptors) as platformDesc:
                with platformDesc.DescriptorSetInformation() as descSetInfo:
                    descSetInfo.bMS_VendorCode = 1

                    with descSetInfo.SetHeaderDescriptor() as setHeader:
                        with setHeader.SubsetHeaderConfiguration() as subsetConfig:
                            subsetConfig.bConfigurationValue = 0

                            for i in self.winusb_interfaces:
                                with subsetConfig.SubsetHeaderFunction() as subsetFunc0:
                                    subsetFunc0.bFirstInterface = i
                    
                                    with subsetFunc0.FeatureCompatibleID() as compatID:
                                        compatID.CompatibleID = 'WINUSB'
                                        compatID.SubCompatibleID = ''
                                    
                                    if i in self.device_interface_guids:
                                        with subsetFunc0.FeatureRegProperty() as deviceInterfaceGUID:
                                            deviceInterfaceGUID.wPropertyDataType = 1
                                            deviceInterfaceGUID.PropertyName = 'DeviceInterfaceGUID'
                                            deviceInterfaceGUID.PropertyData = '{' + str(self.device_interface_guids[i]) + '}'

        windowsRequestHandler = WindowsRequestHandler(platformDescriptors)
        usb_control_handlers.append(windowsRequestHandler)
