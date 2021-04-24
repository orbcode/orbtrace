import nmigen

from litex.soc.interconnect.axi import AXILiteInterface

from .. import usb_mem_bridge

class MemRequestHandler:
    def __init__(self):
        self._axi_lite = nmigen.Record(
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
    
    def wrap(self, wrapper):
        wrapper.connect(self.axi_lite.aw.addr, self._axi_lite.aw.addr)
        wrapper.connect(self.axi_lite.aw.valid, self._axi_lite.aw.valid)
        wrapper.connect(self.axi_lite.aw.ready, self._axi_lite.aw.ready)

        wrapper.connect(self.axi_lite.w.data, self._axi_lite.w.data)
        wrapper.connect(self.axi_lite.w.strb, self._axi_lite.w.strb)
        wrapper.connect(self.axi_lite.w.valid, self._axi_lite.w.valid)
        wrapper.connect(self.axi_lite.w.ready, self._axi_lite.w.ready)

        wrapper.connect(self.axi_lite.b.resp, self._axi_lite.b.resp)
        wrapper.connect(self.axi_lite.b.valid, self._axi_lite.b.valid)
        wrapper.connect(self.axi_lite.b.ready, self._axi_lite.b.ready)

        wrapper.connect(self.axi_lite.ar.addr, self._axi_lite.ar.addr)
        wrapper.connect(self.axi_lite.ar.valid, self._axi_lite.ar.valid)
        wrapper.connect(self.axi_lite.ar.ready, self._axi_lite.ar.ready)

        wrapper.connect(self.axi_lite.r.resp, self._axi_lite.r.resp)
        wrapper.connect(self.axi_lite.r.data, self._axi_lite.r.data)
        wrapper.connect(self.axi_lite.r.valid, self._axi_lite.r.valid)
        wrapper.connect(self.axi_lite.r.ready, self._axi_lite.r.ready)
