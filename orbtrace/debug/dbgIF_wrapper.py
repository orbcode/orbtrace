from amaranth                  import *

class DBGIF(Elaboratable):
    def __init__(self, dbgif, glue):
        self.addr32       = glue.from_migen(dbgif.addr32)
        self.rnw          = glue.from_migen(dbgif.rnw)
        self.apndp        = glue.from_migen(dbgif.apndp)
        self.dwrite       = glue.from_migen(dbgif.dwrite)
        self.dread        = glue.from_migen(dbgif.dread)
        self.perr         = glue.from_migen(dbgif.perr)
        self.go           = glue.from_migen(dbgif.go)
        self.done         = glue.from_migen(dbgif.done)
        self.ack          = glue.from_migen(dbgif.ack)
        self.pinsin       = glue.from_migen(dbgif.pinsin)
        self.pinsout      = glue.from_migen(dbgif.pinsout)
        self.command      = glue.from_migen(dbgif.command)
        self.dev          = glue.from_migen(dbgif.dev)
        self.is_jtag      = glue.from_migen(dbgif.is_jtag)

    def elaborate(self, platform):
        m = Module()

        return m
