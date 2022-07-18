USB Power Interface
===================

The power interface is identified by ``bInterfaceClass = 0xff`` and ``bInterfaceSubclass = 0x50 ('P')``.

Control Requests
----------------

Control requests are vendor-specific interface-directed, i.e. with ``bmRequestType = 0x41 or 0xc1``
and the lower half of ``wIndex`` containing ``bInterfaceNumber``.

Set enable
^^^^^^^^^^

=============  ========  =======  ===============================  =======
bmRequestType  bRequest  wValue   wIndex                           wLength
=============  ========  =======  ===============================  =======
0x41           0x01      Enable   Channel << 8 | bInterfaceNumber  0
=============  ========  =======  ===============================  =======

=======  =======================
Channel  Description
=======  =======================
0x00     VTREF
0x01     VTPWR
0xFF     All channels
=======  =======================

Set voltage
^^^^^^^^^^^

=============  ========  =======  ===============================  =======
bmRequestType  bRequest  wValue   wIndex                           wLength
=============  ========  =======  ===============================  =======
0x41           0x02      Voltage  Channel << 8 | bInterfaceNumber  0
=============  ========  =======  ===============================  =======

=======  =======================
Channel  Description
=======  =======================
0x00     VTREF
0x01     VTPWR
=======  =======================

Voltage is expressed in millivolts.

Get status
^^^^^^^^^^

=============  ========  =======  ================  =======
bmRequestType  bRequest  wValue   wIndex            wLength
=============  ========  =======  ================  =======
0xc1           TBD       TBD      bInterfaceNumber  TBD
=============  ========  =======  ================  =======
