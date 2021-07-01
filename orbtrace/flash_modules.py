from litespi.spi_nor_flash_module import SpiNorFlashModule
from litespi.opcodes import SpiNorFlashOpCodes
from litespi.ids import SpiNorFlashManufacturerIDs

class IS25LP256D(SpiNorFlashModule):
    manufacturer_id = SpiNorFlashManufacturerIDs.ISSI
    device_id = 0x6019
    name = "is25lp256d"

    total_size  =   33554432   # bytes
    page_size   =        256   # bytes
    total_pages =     131072

    supported_opcodes = [
        SpiNorFlashOpCodes.READ_1_1_1,
        SpiNorFlashOpCodes.PP_1_1_1,
        SpiNorFlashOpCodes.READ_1_1_2,
        SpiNorFlashOpCodes.PP_1_1_2,
        SpiNorFlashOpCodes.READ_1_1_4,
        SpiNorFlashOpCodes.PP_1_1_4,
        SpiNorFlashOpCodes.READ_1_4_4,
    ]
    dummy_bits = 24

class S25FL064L(SpiNorFlashModule):
    manufacturer_id = SpiNorFlashManufacturerIDs.SPANSION
    device_id = 0x6017
    name = "s25fl064l"

    total_size  =    8388608   # bytes
    page_size   =        256   # bytes
    total_pages =      32768

    supported_opcodes = [
        SpiNorFlashOpCodes.READ_1_1_1,
        SpiNorFlashOpCodes.PP_1_1_1,
        SpiNorFlashOpCodes.READ_1_1_1_FAST,
        SpiNorFlashOpCodes.READ_1_1_2,
        SpiNorFlashOpCodes.PP_1_1_2,
        SpiNorFlashOpCodes.READ_1_1_4,
        SpiNorFlashOpCodes.PP_1_1_4,
        SpiNorFlashOpCodes.READ_1_1_1_4B,
        SpiNorFlashOpCodes.PP_1_1_1_4B,
        SpiNorFlashOpCodes.READ_1_1_1_FAST_4B,
        SpiNorFlashOpCodes.READ_1_1_2_4B,
        SpiNorFlashOpCodes.READ_1_1_4_4B,
        SpiNorFlashOpCodes.PP_1_1_4_4B,
        SpiNorFlashOpCodes.READ_1_4_4,
    ]
    dummy_bits = 40
