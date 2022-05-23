import os
f = open("numbers.bin", "wb")
for x in range(0,4030):
    f.write(bytes([x%256]))
f.close()
os.system('arm-none-eabi-objcopy --change-section-address .data=0x08000000 -I binary -O elf32-littlearm numbers.bin numbers.elf')
