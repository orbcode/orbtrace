ORBTrace Development
====================

This is the repository for the ORBTrace debug tool, targetting ARM CORTEX JTAG & SWD debug and  parallel TRACE.

The current gateware runs on the ECPIX-5 development board and (optional) breakout board which you can find in the `lcd/bob' directory. You can use Orbtrace without this breakout board, but there will be a lot of flying wires around and you're unlikely to reach the maximum speeds that are possible.

Alongside the TRACE capability, ORBTrace is one of the fastest CMSIS-DAP interfaces on the planet. Here's the results of some simple testing;

![Table](https://raw.githubusercontent.com/orbcode/orbtrace/main/docs/source/resources/performance.png)

On the Debug side the gateware exports cmsis-dap v1 and v2 interfaces. These have been validated against BlackMagic Probe and pyOCD. Information about success with other cmsis-dap clients gratefully received (and bug reports too, so we can fix them).

On the TRACE side primary the gateware exports a USB-Bulk endpoint carrying 1-4 bit TRACE data. Testing is against Orbuculum.

Full documentation for Orbtrace is available via Read The Docs at https://orbtrace.readthedocs.io/en/latest/.

Building
--------

`./orbtrace_builder.py --platform orbtrace_mini --build`

(You might also want `--profile dfu` and `--profile test` if you're working on those elements. They build in separate directories.)

To burn application firmware using boot button hold down the boot button while powring on the device (Status goes purple), then;

`dfu-util -d 1209:3443 -a 1 -D build/orbtrace_mini/gateware/orbtrace_mini.bit`

and power cycle.

in addition...To ensure everything is up to date;

```
rm -rf build
git pull --recurse-submodules
```

To burn bootloader and application using openFPGALoader;

`openFPGALoader -c ft232 -f -o 0x0 build/orbtrace_mini_dfu/gateware/orbtrace_mini.bit`

and

`openFPGALoader -c ft232 -f -o 0x100000 build/orbtrace_mini/gateware/orbtrace_mini.bit`

You may need udev rules, in which case add a file 99-orbtrace.rules into /etc/udev/rules.d with the following contents;

```
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1209", ATTRS{idProduct}=="3443", GROUP="plugdev", MODE="0666"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1209", ATTRS{idProduct}=="3442", GROUP="plugdev", MODE="0666"
```

...you can then activate the new rules with `sudo udevadm control --reload-rules && sudo udevadm trigger`.

Thanks and stuff
----------------

Orbtrace is built on top of a whole slew of other projects, and it simply wouldn't be possible without the effort of literally hundreds of very smart people across the net. Thanks are due to all of them for contributing to the common good that is Open Source. You are more than welcome to use the material here, but whatever the words of the various licences attached to these files, on your honour please respect the Open Source ethos, pay it forward, and go out of your way to be nice to others.
