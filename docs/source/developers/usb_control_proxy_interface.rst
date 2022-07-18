USB Control Proxy Interface
===========================

The control proxy interface is identified by ``bInterfaceClass = 0xff`` and ``bInterfaceSubclass = 0x58 ('X')``.

Certain operating systems (e.g. Windows) disallows issuing control requests to an interface that's already claimed for bulk transfer by another process.
To allow e.g. configuring the :ref:`usb_trace_interface` while it's already opened for capture, this interface is provided as a workaround.

Control Requests
----------------

Control requests are vendor-specific interface-directed, i.e. with ``bmRequestType = 0x41 or 0xc1``
and the lower half of ``wIndex`` containing the ``bInterfaceNumber`` of this interface.

``bRequest`` has a range for each supported target interface with an associated offset.
When a request is handled, the offset is subtracted from ``bRequest`` and the request is forwarded to the target interface's handler.


==============  ======  ==========================
bRequest range  Offset  Target interface
==============  ======  ==========================
0x01 - 0x0f     0x00    :ref:`usb_trace_interface`
==============  ======  ==========================
