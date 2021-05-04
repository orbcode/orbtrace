Purpose
=======

Orbtrace performs two essential functions, with a number of other supporting bits and pieces around the edges. Specifically it;

1. Presents a *Debug Interface* to which CMSIS-DAP v1 or v2 compliant interface software can attach, to control and debug the target device over either a SWD or JTAG interface.
2. Collects data from the *Parallel Trace Port* of the target device over a 1, 2 or 4 bit parallel interface and presents it to software on the host PC. These data can be used for reporting on the progress of the software running on the target device, and also reconstruct it's recent actions.

In addition to the above, Orbtrace can also, depending on the hardware it's running on, provide power to the target and measure its current consumption during program execution, it can also provide secondary serial links to the target.  All of these data streams are carried over a single USB2-HS communnication link.

In respect of (1) above, typically software that would communicate with Orbtrace would be [BlackMagic Probe](https:https://github.com/blacksphere/blackmagic) or [PyOCD](https://github.com/pyocd/pyOCD). These would then connect to 


.. mermaid::

    sequenceDiagram
      participant Alice
      participant Bob
      Alice->John: Hello John, how are you?
      loop Healthcheck
          John->John: Fight against hypochondria
      end
      Note right of John: Rational thoughts <br/>prevail...
      John-->Alice: Great!
      John->Bob: How about you?
      Bob-->John: Jolly good!
