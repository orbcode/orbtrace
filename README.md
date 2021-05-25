ORBTrace Development
====================

This is the repository for the ORBTrace debug tool, targetting ARM CORTEX JTAG & SWD debug and  parallel TRACE.

The current gateware runs on the ECPIX-5 development board and (optional) breakout board which you can find in the `lcd/bob' directory. You can use Orbtrace without this breakout board, but there will be a lot of flying wires around and you're unlikely to reach the maximum speeds that are possible.

Alongside the TRACE capability, ORBTrace is one of the fastest CMSIS-DAP interfaces on the planet. Here's the results of some simple testing;

![Table](https://raw.githubusercontent.com/orbcode/orbuculum/main/docs/source/resources/performance.png)

On the Debug side the gateware exports cmsis-dap v1 and v2 interfaces. These have been validated against BlackMagic Probe and pyOCD. Information about success with other cmsis-dap clients gratefully received (and bug reports too, so we can fix them).

On the TRACE side primary the gateware exports a USB-Bulk endpoint carrying 1-4 bit TRACE data. Testing is against Orbuculum.

Full documentation for Orbtrace is available via Read The Docs at https://orbtrace.readthedocs.io/en/latest/.

Orbtrace is built on top of a whole slew of other projects, and it simply wouldn't be possible without the effort of literally hundreds of very smart people across the net. Thanks are due to all of them for contributing to the common good that is Open Source. You are more than welcome to use the material here, but whatever the words of the various licences attached to these files, on your honour please respect the Open Source ethos, pay it forward, and go out of your way to be nice to others.
