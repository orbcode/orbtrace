Purpose
=======

Orbtrace performs two essential functions, with a number of other supporting bits and pieces around the edges. Specifically it;

1. Presents a *Debug Interface* to which CMSIS-DAP v1 or v2 compliant interface software can attach, to control and debug a target device over either a SWD or JTAG interface.
2. Collects data from the *Parallel Trace Port* of the target device over a 1, 2 or 4 bit interface and presents it to software on the host PC. These data can be used for reporting on the progress of the software running on the target device, and optionally to reconstruct it's recent actions.

In addition to the above, Orbtrace can also, depending on the hardware it's running on, provide power to the target and measure its current consumption during program execution. It can also provide secondary serial links.  All of these data streams are carried over a single USB2-HS communnication link between Orbtrace and the host PC.

The normal connection between Orbtrace and the target is the 2x10-way 0.05" connector you will see on the target PCB.  When doing debug only (i.e. no tracing functions) then the smaller 2x5-way 0.05" connector is typically used instead. Details on these connectors are available from the `Keil Website <https://www2.keil.com/coresight/coresight-connectors>`_.

In respect of (1) above, typically software that would communicate with Orbtrace would be `BlackMagic Probe <https://github.com/blacksphere/blackmagic>`_ or `PyOCD <https://github.com/pyocd/pyOCD>`_. These would then connect to a debugger such as gdb.

.. mermaid::

    graph LR
        A(Target) -- JTAG or SWD ---- B((Orbtrace))
        A -- TRACE --> B((Orbtrace))
        A -- Serial ---- B((Orbtrace))
        B -- USB-HS ---- Z[Demux]
        
        subgraph Host PC
            Z --- C(Debug Server) -- gdb remote protocol --- G(GDB)
            Z --> D(Orbuculum)
            Z --- H(Serial Server)
            D -- Socket --> E(Orb Client 1)
            D -- Socket --> F(Orb Client n)
            H -- ACM --- I(Serial Client)
        end

        classDef green fill:#9f6,stroke:#333,stroke-width:2px;
        classDef yellow fill:#ffff00,stroke:#333,stroke-width:2px;
        classDef blue fill:#00f0ff,stroke:#333,stroke-width:2px;
        classDef pink fill:#ffB0ff,stroke:#333,stroke-width:2px;
        classDef brown fill:#bfb01f,stroke:#333,stroke-width:2px;
        class A green
        class B yellow
        class C,G blue
        class D,E,F pink
        class H,I brown
        

In respect of (2) above, exploiting the trace flow from Orbtrace, the reader is directed to the `Orbuculum <https://github.com/orbcode/orbuculum>`_ suite for detailed information.