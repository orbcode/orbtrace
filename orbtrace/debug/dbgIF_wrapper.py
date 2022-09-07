from amaranth                  import *

class DBGIF(Elaboratable):
    def __init__(self, dbgif, wrapper):
        self.addr32       = wrapper.from_migen(dbgif.addr32)
        self.rnw          = wrapper.from_migen(dbgif.rnw)
        self.apndp        = wrapper.from_migen(dbgif.apndp)
        self.dwrite       = wrapper.from_migen(dbgif.dwrite)
        self.dread        = wrapper.from_migen(dbgif.dread)
        self.perr         = wrapper.from_migen(dbgif.perr)
        self.go           = wrapper.from_migen(dbgif.go)
        self.done         = wrapper.from_migen(dbgif.done)
        self.ack          = wrapper.from_migen(dbgif.ack)
        self.pinsin       = wrapper.from_migen(dbgif.pinsin)
        self.pinsout      = wrapper.from_migen(dbgif.pinsout)
        self.command      = wrapper.from_migen(dbgif.command)
        self.dev          = wrapper.from_migen(dbgif.dev)
        self.is_jtag      = wrapper.from_migen(dbgif.is_jtag)

    def elaborate(self, platform):
        m = Module()

        return m
