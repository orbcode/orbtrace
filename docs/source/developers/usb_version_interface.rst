USB Version Interface
=====================

The version interface is identified by ``bInterfaceClass = 0xff`` and ``bInterfaceSubclass = 0x56 ('V')``.

The interface string of the version interface contains the version of the current gateware build, as per ``git describe --always --long --dirty``.

Example: ``Version: v1.0.0-0-g3ad3fa4``

Control Requests
----------------

The version interface currently has no defined control requests.
