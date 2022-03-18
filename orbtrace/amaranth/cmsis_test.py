import datetime
import argparse
import usb.backend.libusb1
import hid

IS_V1 = 0
SERIAL = 0
VENDOR_ID = 0x1209
PRODUCT_ID = 0x3443
if (~IS_V1):
    INTERFACE = 4
    IN_EP = (5|0x80)
    OUT_EP = 3
else:
    INTERFACE = 3
    IN_EP = (4|0x80)
    OUT_EP = 2



def write_to_usb(dev, msg_str):

    print(">>>",end="")
    for p in msg_str:
        print(f' 0x{p:02x}', end="")

    try:
        num_bytes_written = dev.write(OUT_EP, msg_str)

    except usb.core.USBError as e:
        print (e.args)

    print(f" [{num_bytes_written}]")
    return num_bytes_written

def read_from_usb(dev, rxlen, timeout):
    try:
	# try to read a maximum of 2^16-1 bytes from 0x81 (IN endpoint)
        data = dev.read(IN_EP, 60000, timeout)
    except usb.core.USBError as e:
        print ("Error reading response: {}".format(e.args))
        exit(-1)

    if len(data) == 0:
        print ("Zero length response")
        exit(-1)

    return data

def write_to_hid(dev, msg_str):

#    print(">>>",end="")
#    for p in msg_str:
#        print(f' 0x{p:02x}', end="")

    byte_str = b'\0' + bytes(msg_str) + b'\0' * max(64 - len(msg_str), 0)

    device.write(byte_str)
    print()

def op_response( d, compareStr ):
    duff=False
    print(" <<<"+str(len(d))+f" bytes [",end="")
    for p,x in zip(d,compareStr):
        if p==x:
            print(f' 0x{p:02x}', end="")
        else:
            duff=True
            print(f' Got:0x{p:02x}/0x{x:02x}!!', end="")
    if (duff):
        print(" ] *********************** FAULT **********************")
    else:
        print(" ]")


tdests = (
    ( "Short Request",              b"\x19\x19",                    b"\xff"                     ),
    ( "Vendor ID",                  b"\x00\x01",                    b"\x00\x00"                 ),
    ( "Product ID",                 b"\x00\x02",                    b"\x00\x00"                 ),
    ( "Serial Number",              b"\x00\x03",                    b"\x00\x00"                 ),
    ( "Target Device Vendor",       b"\x00\x05",                    b"\x00\x00"                 ),
    ( "Target Device Name",         b"\x00\x06",                    b"\x00\x00"                 ),
    ( "FW version",                 b"\x00\x04",                    b"\x00\x06\x32\x2e\x31\x2e\x30" ),
    ( "Illegal command",            b"\x42",                        b"\xff"                     ),
    ( "Request CAPABILITIES",       b"\x00\xf0",                    b"\x00\x01\x03"             ),
    ( "Request TEST DOMAIN TIMER",  b"\x00\xf1",                    b"\x00\x08\x00\xca\x9a\x3b" ),
    ( "Request SWO Trace Buffer Size", b"\x00\xfd",                 b"\xff"                     ),
    ( "Request Packet Count",       b"\x00\xFE",                    b"\x00\x01\x01"             ),
    ( "Request Packet Size",        b"\x00\xff",                    b"\x00\x02\xfc\x01"         ),
    ( "Set connect led",            b"\x01\x00\x01",                b"\x01\x00"                 ),
    ( "Set running led",            b"\x01\x01\x01",                b"\x01\x00"                 ),
    ( "Set illegal led",            b"\x01\x02\x01",                b"\xff"                     ),
    ( "Connect swd",                b"\x02\x01",                    b"\x02\x01"                 ),
    ( "Disconnect",                 b"\x03",                        b"\x03\x00"                 ),
    ( "Connect default",            b"\x02\x00",                    b"\x02\x01"                 ),
    ( "Disconnect",                 b"\x03",                        b"\x03\x00"                 ),
    ( "Connect JTAG",               b"\x02\x02",                    b"\x02\x02"                 ),
    ( "Disconnect",                 b"\x03",                        b"\x03\x00"                 ),
    ( "Connect swd",                b"\x02\x01",                    b"\x02\x01"                 ),
    ( "WriteABORT",                 b"\x08\x00\x01\x02\x03\x04",    b"\x08\x00"                 ),
    ( "Delay",                      b"\x09\x00\xff",                b"\x09\x00"                 ),
    ( "ResetTarget",                b"\x0A" ,                       b"\x0A\x00\x00"             ),
    ( "DAP_SWJ_Pins",               b"\x10\xff\xff\x00\xff\x02\x00", b"\x10\x77"                ),
    ( "DAP_SWJ_Clock",              b"\x11\x00\x01\x02\x03",        b"\x11\x00"                 ),
    ( "DAP_SWJ_Sequence",           b"\x12\x03\x01",    b"\x12\x00"                 ),
    ( "DAP_SWJ_Sequence (Long)",    b"\x12\x00\x01\x02\x03\x04\x01\x02\x03\x04\x01\x02\x03\x04\x01\x02\x03\x04\x01\x02\x03\x04\x01\x02\x03\x04\x01\x02\x03\x04\x01\x02\x03\x04",    b"\x12\x00"                 ),
    ( "DAP_SWO_Transport (None)",   b"\x17\x00",                    b"\xff"                 ),
    ( "DAP_SWO_Transport (Cmd)",    b"\x17\x01",                    b"\xff"                 ),
    ( "DAP_SWO_Transport (EP)",     b"\x17\x02",                    b"\xff"                 ),
    ( "DAP_SWO_Transport (Bad)",    b"\x17\x03",                    b"\xff"                 ),
    ( "DAP_SWO_Mode (Off)",         b"\x18\x00",                    b"\xff"                 ),
    ( "DAP_SWO_Mode (Uart)",        b"\x18\x01",                    b"\xff"                 ),
    ( "DAP_SWO_Mode (Manch)",       b"\x18\x02",                    b"\xff"                 ),
    ( "DAP_SWO_Mode (Bad)",         b"\x18\x03",                    b"\xff"                 ),
    ( "DAP_SWO_Baudrate",           b"\x19\x01\x02\x03\x04",        b"\xff"                 ),
    ( "DAP_SWO_Control (Start)",    b"\x1a\x01",                    b"\xff"                 ),
    ( "DAP_SWO_Control (Stop)",     b"\x1a\x00",                    b"\xff"                 ),
    ( "DAP_SWO_Control (Bad)",      b"\x1a\x02",                    b"\xff"                 ),
    ( "DAP_SWO_Status",             b"\x1b",                        b"\xff"                 ),
    ( "DAP_SWO_ExtendedStatus",     b"\x1e\x07",                    b"\xff"                 ),
    ( "DAP_SWO_ExtendedStatus (Bad)", b"\x1e\x08",                  b"\xff"                 ),
    ( "DAP_SWO_Data (Short)",       b"\x1c\x04\x00",                b"\xff"                 ),
    ( "DAP_SWO_Data (Long)",        b"\x1c\x63\x00",                b"\xff"                 ),
    ( "DAP_SWO_Data (Too Long)",    b"\x1c\x65\x00",                b"\xff"                 ),

    ( "DAP_SWD_Sequence (Simple)",  b"\x1d\x01\x88",                b"\x1d\x00" ),
    ( "DAP_JTAG_Configure",         b"\x15\x01\x04",                b"\x15\x00" ),

    ( "DAP_SWD_Sequence (Null)",  b"\x1d\x00",                b"\x1d\x00" ),
    ( "DAP_SWD_Sequence (Read)",  b"\x1d\x01\x86",                b"\x1d\x00\x3f" ),
    ( "DAP_SWD_Sequence (Readx2)",  b"\x1d\x02\x85\x83",                b"\x1d\x00\x1f\x07" ),
    ( "DAP_SWD_Sequence (Readx255)",  b"\x1d\xff\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88\x81\x82\x83\x84\x85\x86\x87\x88",
      b"\x1d\x00\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff\x01\x03\x07\x0f\x1f\x3f\x7f\xff"),

    ( "DAP_SWD_Sequence (Readx1, 9 bits)",  b"\x1d\x01\x89", b"\x1d\x00\xff\x01" ),
    ( "DAP_SWD_Sequence (Readx1, 8 bits)",  b"\x1d\x01\x88", b"\x1d\x00\xff" ),
    ( "DAP_SWD_Sequence (Readx2, 9 bits,3 bits)",  b"\x1d\x02\x89\x83", b"\x1d\x00\xff\x01\x07" ),
    ( "DAP_SWD_Sequence (Readx1, 64 bits)",  b"\x1d\x01\x80", b"\x1d\x00\xff\xff\xff\xff\xff\xff\xff\xff" ),
    ( "DAP_SWD_Sequence (Writex1, 5 bits)",  b"\x1d\x01\x05\x0f",                b"\x1d\x00" ),
    ( "DAP_SWD_Sequence (Writex1, 9 bits)",  b"\x1d\x01\x09\x00\x01",                b"\x1d\x00" ),

    ( "DAP_SWD_Sequence (Writex2, 5 bits, 4 bits)",  b"\x1d\x02\x05\x04\x04\x08",                b"\x1d\x00" ),
    ( "DAP_SWD_Sequence (Writex2, 5 bits, 4 bits, Readx1,5 bits)",  b"\x1d\x03\x05\x04\x04\x08\x85", b"\x1d\x00\x1f" ),


    ( "Connect JTAG",               b"\x02\x02",                    b"\x02"                     ),
    ( "DAP_JTAG_Sequence (Simple Read)",b"\x14\x01\x87\xff",       b"\x14\x00\x00" ),

    ( "DAP_JTAG_Sequence (Simple Read)",b"\x14\x01\x88\xff",       b"\x14\x00\x00" ),
    ( "DAP_JTAG_Sequence (Simple Read, Longer)",b"\x14\x01\x89\xff\xff",       b"\x14\x00\x00\x00" ),
    ( "DAP_JTAG_Sequence (Simple Write)",b"\x14\x01\x08\xff",       b"\x14\x00" ),
    ( "DAP_JTAG_Sequence (Simple Write, Longer)",b"\x14\x01\x08\xff\xff",       b"\x14\x00" ),
    ( "DAP_JTAG_Sequence (2xTDO & Read)",b"\x14\x02\x8a\xff\xff\x03\xff",       b"\x14\x00\x00\x00" ),
    ( "DAP_JTAG_Sequence (Long)",   b"\x14\x01\x80\x00\x00\x00\x00\x00\x00\x00\x00",b"\x14\x00\x00\x00\x00\x00\x00\x00\x00\x00" ),
   ( "DAP_TransferConfigure",      b"\x04\x03\x11\x22\x33\x44",    b"\x04\x00" ),
    ( "DAP_TransferConfigure (Bad)",b"\x04\x03\x11\x22\x33",        b"\xff" ),


)

tests = (
    ( "FW version",                 b"\x00\x04",                    b"\x00\x06\x32\x2e\x31\x2e\x30" ),
    ( "Connect JTAG",   b"\x02\x02", b"\x02\x02" ),
    ( "Set IR Len", b"\x15\x02\x04\x05", b"\x15\x00" ),
    ( "Read"      , b"\x05\x00\x01\x02\x02\x02", b"\x05\x03\x01\x77\x14\xa0\x2b\x77\x14\xa0\x2b\x77\x14\xa0\x2b" ),
    ("Read with AP",      b"\x05\x00\x03\x02\x0b\x02", b"\x05\x03\x01\x77\x14\xa0\x2b\x00\x00\x00\x00\x77\x14\xa0\x2b" ),
#    ("Read AP last",      b"\x05\x00\x01\x0b", b"\x05\x01\x01\x00\x00\x00\x00" ),
    #( "Write"     , b"\x05\x00\x01\x04\x00\x00\x00\x70", b"\x05\x01\x01" ),
    #("Write+Read",      b"\x05\x00\x02\x02\x08\x00\x00\x00\x00\x04\x04\x04\x04", b"\x05\x01\x01" ),
 #   (" Observed Issue", b"\x05\x00\x02\x08\xf0\x00\x00\x00\x0f", b"\x05\x02\x01\x11\x00\x77\x24" ),

)

if (IS_V1):
    device = hid.device()
    device.open(VENDOR_ID, PRODUCT_ID)
else:
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    u=usb.util.claim_interface(device, INTERFACE)

if device is None:
    raise ValueError('Device not found. Please ensure it is connected')
    sys.exit(1)

print("Interface claimed")

a=datetime.datetime.now()
for desc,inseq,outsq in tests:
    print("==============",desc)

    if (IS_V1):
        write_to_hid(device, inseq)
        r=device.read(127)
    else:
        write_to_usb(device,bytes(inseq))
        r=read_from_usb(device,len(outsq),1000)

    op_response(r,bytes(outsq))
print ("Elapsed Time=",datetime.datetime.now()-a)
