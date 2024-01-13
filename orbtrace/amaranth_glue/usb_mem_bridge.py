import amaranth

from litex.soc.interconnect.axi import AXILiteInterface

from .. import usb_mem_bridge

class MemRequestHandler:
    def __init__(self):
        self._axi_lite = amaranth.Record(
            [
                ('aw', [
                    ('addr', 32),
                    ('valid', 1),
                    ('ready', 1),
                ]),
                ('w', [
                    ('data', 32),
                    ('strb', 4),
                    ('valid', 1),
                    ('ready', 1),
                ]),
                ('b', [
                    ('resp', 2),
                    ('valid', 1),
                    ('ready', 1),
                ]),
                ('ar', [
                    ('addr', 32),
                    ('valid', 1),
                    ('ready', 1),
                ]),
                ('r', [
                    ('resp', 2),
                    ('data', 32),
                    ('valid', 1),
                    ('ready', 1),
                ]),
            ],
        )

        self.axi_lite = AXILiteInterface(clock_domain = 'usb')

        self.handler = usb_mem_bridge.MemRequestHandler(self._axi_lite)
    
    def wrap(self, glue):
        glue.connect(self.axi_lite.aw.addr, self._axi_lite.aw.addr)
        glue.connect(self.axi_lite.aw.valid, self._axi_lite.aw.valid)
        glue.connect(self.axi_lite.aw.ready, self._axi_lite.aw.ready)

        glue.connect(self.axi_lite.w.data, self._axi_lite.w.data)
        glue.connect(self.axi_lite.w.strb, self._axi_lite.w.strb)
        glue.connect(self.axi_lite.w.valid, self._axi_lite.w.valid)
        glue.connect(self.axi_lite.w.ready, self._axi_lite.w.ready)

        glue.connect(self.axi_lite.b.resp, self._axi_lite.b.resp)
        glue.connect(self.axi_lite.b.valid, self._axi_lite.b.valid)
        glue.connect(self.axi_lite.b.ready, self._axi_lite.b.ready)

        glue.connect(self.axi_lite.ar.addr, self._axi_lite.ar.addr)
        glue.connect(self.axi_lite.ar.valid, self._axi_lite.ar.valid)
        glue.connect(self.axi_lite.ar.ready, self._axi_lite.ar.ready)

        glue.connect(self.axi_lite.r.resp, self._axi_lite.r.resp)
        glue.connect(self.axi_lite.r.data, self._axi_lite.r.data)
        glue.connect(self.axi_lite.r.valid, self._axi_lite.r.valid)
        glue.connect(self.axi_lite.r.ready, self._axi_lite.r.ready)
