.. _usb_trace_interface:

USB Trace Interface
===================

The trace interface is identified by ``bInterfaceClass = 0xff`` and ``bInterfaceSubclass = 0x54 ('T')``.
It may have multiple alternate settings with different ``bInterfaceProtocol`` values to support different trace protocols.
Host software negotiates protocol by reading the list of supported alternate settings and selecting the preferred one.

Control Requests
----------------

Control requests are vendor-specific interface-directed, i.e. with ``bmRequestType = 0x41 or 0xc1``
and the lower half of ``wIndex`` containing ``bInterfaceNumber``.

Set Input Format
^^^^^^^^^^^^^^^^

=============  ========  ======  ================  =======
bmRequestType  bRequest  wValue  wIndex            wLength
=============  ========  ======  ================  =======
0x41           0x01      Type    bInterfaceNumber  0
=============  ========  ======  ================  =======


=====  ==============================
Type   Description
=====  ==============================
0x00   Disabled
0x01   1-bit synchronous
0x02   2-bit synchronous
0x03   4-bit synchronous
0x10   Manchester asynchronous (ITM)
0x11   Manchester asynchronous (TPIU)
0x12   NRZ asynchronous (ITM)
0x13   NRZ asynchronous (TPIU)
=====  ==============================

Set Async Baudrate
^^^^^^^^^^^^^^^^^^

=============  ========  ======  ================  =======
bmRequestType  bRequest  wValue  wIndex            wLength
=============  ========  ======  ================  =======
0x41           0x02      0x00    bInterfaceNumber  4
=============  ========  ======  ================  =======

Payload is baudrate as a 32-bit little endian integer.

Protocols
---------

Undefined
^^^^^^^^^

==================  ==================  ==================
bInterfaceClass     bInterfaceSubclass  bInterfaceProtocol
==================  ==================  ==================
0xff                0x54                0x00
==================  ==================  ==================

Trace interfaces with undefined protocol should be used by devices not aware of the format of the data stream (e.g. when capturing raw SWO).
In this case, the user is expected to manually configure the host software for the correct format.

TPIU
^^^^

==================  ==================  ==================
bInterfaceClass     bInterfaceSubclass  bInterfaceProtocol
==================  ==================  ==================
0xff                0x54                0x01
==================  ==================  ==================

This protocol uses one endpoint that will send one or more 16-byte TPIU frames per transfer.
TPIU frames are aligned to USB transfer boundaries.

.. 
    TODO: Insert reference to TPIU frame structure in ARM spec.

.. _usb_itm:

ITM
^^^

==================  ==================  ==================
bInterfaceClass     bInterfaceSubclass  bInterfaceProtocol
==================  ==================  ==================
0xff                0x54                TBD
==================  ==================  ==================

TBD

.. _usb_etm:

ETM
^^^

==================  ==================  ==================
bInterfaceClass     bInterfaceSubclass  bInterfaceProtocol
==================  ==================  ==================
0xff                0x54                TBD
==================  ==================  ==================

TBD

ITM + ETM
^^^^^^^^^

==================  ==================  ==================
bInterfaceClass     bInterfaceSubclass  bInterfaceProtocol
==================  ==================  ==================
0xff                0x54                TBD
==================  ==================  ==================

This protocol provides both an :ref:`usb_itm` and an :ref:`usb_etm` endpoint.
Refer to the respective sections for details.