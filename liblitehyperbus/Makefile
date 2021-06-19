include ../include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS = hyperram.o

all: liblitehyperbus.a

liblitehyperbus.a: $(OBJECTS)
	$(AR) crs liblitehyperbus.a $(OBJECTS)

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.o: $(LIBLITEHYPERBUS_DIRECTORY)/%.c
	$(compile)

%.o: %.S
	$(assemble)

.PHONY: all clean

clean:
	$(RM) $(OBJECTS) liblitehyperbus.a .*~ *~
