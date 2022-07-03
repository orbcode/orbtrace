#
# This file is part of usb-protocol.
#
"""
Structures describing Microsoft OS specific functionality descriptors. Versions that support parsing
incomplete binary data are available as `DescriptorType`.Partial, e.g. `DeviceDescriptor.Partial`, and
are collectively available in the `usb_protocol.types.descriptors.partial.microsoft` module.
"""

from enum import IntEnum

import construct
from construct import this, len_

from ..descriptor import DescriptorField
from usb_protocol.types.descriptor import \
    DescriptorNumber, DescriptorFormat
from usb_protocol.types.descriptors.standard import StandardDescriptorNumbers, DeviceCapabilityTypes


class OSDescriptorTypes(IntEnum):
    SET_HEADER = 0
    SUBSET_HEADER_CONFIGURATION = 1
    SUBSET_HEADER_FUNCTION = 2
    FEATURE_COMPATIBLE_ID = 3
    FEATURE_REG_PROPERTY = 4
    FEATURE_MIN_RESUME_TIME = 5
    FEATURE_MODEL_ID = 6
    FEATURE_CCGP_DEVICE = 7
    FEATURE_VENDOR_REVISION = 8


class RegistryTypes(IntEnum):
    REG_SZ = 1
    REG_EXPAND_SZ = 2
    REG_BINARY = 3
    REG_DWORD_LITTLE_ENDIAN = 4
    REG_DWORD_BIG_ENDIAN = 5
    REG_LINK = 6
    REG_MULTI_SZ = 7


class MicrosoftRequests(IntEnum):
    GET_DESCRIPTOR_SET = 7
    SET_ALTERNATE_ENUM = 8


PlatformDescriptor = DescriptorFormat(
    "bLength"               / DescriptorField("Total length of the platform-specific descriptor block"),
    "bDescriptorType"       / DescriptorNumber(StandardDescriptorNumbers.DEVICE_CAPABILITY),
    "bDevCapabilityType"    / construct.Const(DeviceCapabilityTypes.PLATFORM, construct.Int8ul),
    "bReserved"             / construct.Const(0x00, construct.Int8ul),
    "PlatformCapabilityUUID" / construct.Sequence(
            construct.Const(0xd8dd60df, construct.Int32ul),
            construct.Const(0x4589,     construct.Int16ul),
            construct.Const(0x4cc7,     construct.Int16ul),
            construct.Const(0x9cd2,     construct.Int16ub),
            construct.Const(0x659d,     construct.Int16ub),
            construct.Const(0x9e648a9f, construct.Int32ub)
        ),
)

DescriptorSetInformation = DescriptorFormat(
    "dwWindowsVersion"              / DescriptorField("Minimum windows version this set should apply to", default = 0x06030000),
    "wMSOSDescriptorSetTotalLength" / DescriptorField("The byte length of the descriptor set"),
    "bMS_VendorCode"                / DescriptorField("The vendor code to request this descriptor set with"),
    "bAltEnumCode"                  / DescriptorField("A non-zero number if the device may return non-default USB descriptors for enumeration.", default = 0),
)


SetHeaderDescriptor = DescriptorFormat(
    "wLength"          / construct.Const(0x0A, construct.Int16ul),
    "wDescriptorType"  / construct.Const(OSDescriptorTypes.SET_HEADER, construct.Int16ul),
    "dwWindowsVersion" / DescriptorField("Windows version", default = 0x06030000),
    "wTotalLength"     / DescriptorField("The total length of this descriptor set"),
)


SubsetHeaderConfiguration = DescriptorFormat(
    "wLength"             / construct.Const(0x08, construct.Int16ul),
    "wDescriptorType"     / construct.Const(OSDescriptorTypes.SUBSET_HEADER_CONFIGURATION, construct.Int16ul),
    "bConfigurationValue" / DescriptorField("The configuration ID to which this subset applies"),
    "bReserved"           / construct.Const(0x00, construct.Int8ul),
    "wTotalLength"        / DescriptorField("The total length the configuration subset (including header)"),
)


SubsetHeaderFunction = DescriptorFormat(
    "wLength"         / construct.Const(0x08, construct.Int16ul),
    "wDescriptorType" / construct.Const(OSDescriptorTypes.SUBSET_HEADER_FUNCTION, construct.Int16ul),
    "bFirstInterface" / DescriptorField("The first interface number to which this function subset applies"),
    "bReserved"       / construct.Const(0x00, construct.Int8ul),
    "wTotalLength"    / DescriptorField("The total length the function subset (including header)"),
)


FeatureCompatibleID = DescriptorFormat(
    "wLength"         / construct.Const(0x14, construct.Int16ul),
    "wDescriptorType" / construct.Const(OSDescriptorTypes.FEATURE_COMPATIBLE_ID, construct.Int16ul),
    "CompatibleID"    / construct.PaddedString(8, "utf8"),
    "SubCompatibleID" / construct.PaddedString(8, "utf8"),
)


FeatureRegProperty = DescriptorFormat(
    "wLength"             / construct.Rebuild(construct.Int16ul, 10 + (2 + 2*len_(this.PropertyName)) + (2 + 2*len_(this.PropertyData))),
    "wDescriptorType"     / construct.Const(OSDescriptorTypes.FEATURE_REG_PROPERTY, construct.Int16ul),
    "wPropertyDataType"   / DescriptorField("Data type of the registry property"),
    "wPropertyNameLength" / construct.Rebuild(construct.Int16ul, 2 + 2*len_(this.PropertyName)),
    "PropertyName"        / construct.CString("utf_16_le"),
    "wPropertyDataLength" / construct.Rebuild(construct.Int16ul, 2 + 2*len_(this.PropertyData)),
    "PropertyData"        / construct.CString("utf_16_le"),
)


FeatureMinResumeTime = DescriptorFormat(
    "wLength"              / construct.Const(0x06, construct.Int16ul),
    "wDescriptorType"      / construct.Const(OSDescriptorTypes.FEATURE_MIN_RESUME_TIME, construct.Int16ul),
    "bResumeRecoveryTime"  / DescriptorField("Number of milliseconds required to resume the device"),
    "bResumeSignalingTime" / DescriptorField("Number of milliseconds device required for resume signaling to be asserted"),
)


FeatureModelID = DescriptorFormat(
    "wLength"         / construct.Const(0x14, construct.Int16ul),
    "wDescriptorType" / construct.Const(OSDescriptorTypes.FEATURE_MODEL_ID, construct.Int16ul),
    "ModelID"         / construct.Bytes(16),
)


FeatureCCGPDevice = DescriptorFormat(
    "wLength"         / construct.Const(0x04, construct.Int16ul),
    "wDescriptorType" / construct.Const(OSDescriptorTypes.FEATURE_CCGP_DEVICE, construct.Int16ul),
)


FeatureVendorRevision = DescriptorFormat(
    "wLength"         / construct.Const(0x06, construct.Int16ul),
    "wDescriptorType" / construct.Const(OSDescriptorTypes.FEATURE_VENDOR_REVISION, construct.Int16ul),
    "VendorRevision"  / construct.Int16ul,
)

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
