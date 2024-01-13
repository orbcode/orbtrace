# SPDX-License-Identifier: BSD-3-Clause
from amaranth import Elaboratable, Module, Signal, Memory, DomainRenamer
from struct import pack as structPack, unpack as structUnpack
from ......usb_protocol.emitters.descriptors.microsoft import PlatformDescriptorCollection
from luna.gateware.usb.stream import USBInStreamInterface
from typing import Tuple

__all__ = (
	'GetDescriptorSetHandler',
)

class GetDescriptorSetHandler(Elaboratable):
	""" Gateware that handles responding to Windows GET_DESCRIPTOR_SET requests.

	Attributes
	----------
		request : Signal(8), input
			The request field associated with the Get Descriptor Set request.
			Contains the descriptor set's vendor code.
		length : Signal(16), input
			The length field associated with the Get Descriptor Set request.
			Determines the maximum amount allowed in a response.

		start : Signal(), input
			Strobe that indicates when a descriptor should be transmitted.
		startPosition : Signal(11), input
			Specifies the starting position of the descriptor data to be transmitted.

		tx : USBInStreamInterface(), inout
			The USBInStreamInterface that streams our descriptor data.
		stall : Signal(), output
			Pulsed if a STALL handshake should be generated, instead of a response.
	"""
	elementSize = 4

	def __init__(self, descriptorCollection : PlatformDescriptorCollection, maxPacketLength = 64, domain = 'usb'):
		"""
		Parameters
		----------
		descriptorCollection : PlatformDescriptorCollection
			The PlatformDescriptorCollection containing the descriptors to use for Windows responses.
		maxPacketLength: int
			Maximum EP0 packet length.
		domain: string
			The clock domain this generator should belong to. Defaults to 'usb'.
		"""
		self._descriptors = descriptorCollection
		self._maxPacketLength = maxPacketLength
		self._domain = domain

		#
		# I/O port
		#
		self.request = Signal(8)
		self.length = Signal(16)

		self.start = Signal()
		self.startPosition = Signal(11)

		self.tx = USBInStreamInterface()
		self.stall = Signal()

	@classmethod
	def _alignToElementSize(cls, n):
		""" Returns a given number rounded up to the next 'aligned' element size. """
		return (n + (cls.elementSize - 1)) // cls.elementSize

	def generateROM(self) -> Tuple[Memory, int, int]:
		""" Generates a ROM used to hold descriptor sets.

		Notes
		-----
		All data is aligned to 4 byte boundaries.

		This ROM is laid out as follows:

		* Index offsets and descriptor set lengths

			Each index of a descriptor set has an entry consistent of the length
			of the descriptor set (2 bytes) and the address of the first data
			byte (2 bytes).

			+---------+--------------------------------------+
			| Address |                 Data                 |
			+=========+======================================+
			|    0000 | Length of the first descriptor set   |
			+---------+--------------------------------------+
			|    0002 | Address of the first descriptor set  |
			+---------+--------------------------------------+
			|     ... |                                      |
			+---------+--------------------------------------+

		* Data

			Descriptor data for each descriptor set. Padded by 0 to the next 4-byte address.

			+---------+--------------------------------------+
			| Address |                 Data                 |
			+=========+======================================+
			|     ... | Descriptor data                      |
			+---------+--------------------------------------+

		Returns
		-------
		:py:class:`Tuple <tuple>` [ :py:class:`amaranth.hdl.mem.Memory`, :py:class:`int`, :py:class:`int` ]
			A List containing:

				* A Memory object defining the descriptor data and access information as defined above.
				  The memory object uses 32-bit entries which the descriptor gateware accesses accordingly.
				* The length of the largest held descriptor.
				* The highest Vendor code number used by the descriptors for retrieval.
		"""

		descriptors = self._descriptors.descriptors
		assert max(descriptors.keys()) == len(descriptors), "descriptor sets have non-contiguous vendor codes!"
		assert min(descriptors.keys()) == 1, "descriptor sets must start at vendor code 1"

		maxVendorCode = max(descriptors.keys())
		maxDescriptorSize = 0
		romSizeTableEntries = len(descriptors) * self.elementSize

		romSizeDescriptors = 0
		for descriptorSet in descriptors.values():
			alignedSize = self._alignToElementSize(len(descriptorSet))
			romSizeDescriptors += alignedSize * self.elementSize
			maxDescriptorSize = max(maxDescriptorSize, len(descriptorSet))

		totalSize = romSizeTableEntries + romSizeDescriptors
		rom = bytearray(totalSize)

		nextFreeAddress = maxVendorCode * self.elementSize

		# First, generate a list of 'table pointers', which point to the address of each descriptor set, in memory.
		for vendor_code, descriptorSet in sorted(descriptors.items()):
			descriptorSetLen = len(descriptorSet)
			pointerBytes = structPack('>HH', descriptorSetLen, nextFreeAddress)
			pointerAddress = (vendor_code - 1) * self.elementSize
			rom[pointerAddress:pointerAddress + self.elementSize] = pointerBytes
			rom[nextFreeAddress:nextFreeAddress + descriptorSetLen] = descriptorSet

			alignedSize = self._alignToElementSize(descriptorSetLen)
			nextFreeAddress += alignedSize * self.elementSize

		assert totalSize == len(rom)
		elementSize = self.elementSize
		romEntries = (rom[i:i + elementSize] for i in range(0, totalSize, elementSize))
		initialiser = [structUnpack('>I', romEntry)[0] for romEntry in romEntries]
		return Memory(width = 32, depth = len(initialiser), init = initialiser), maxDescriptorSize, maxVendorCode

	def elaborate(self, platform) -> Module:
		""" Describes the specific gateware needed to implement Windows :code:`GET_DESCRIPTOR_SET` requests.

		Parameters
		----------
		platform
			The Amaranth platform for which the gateware will be synthesised.

		Returns
		-------
		:py:class:`amaranth.hdl.dsl.Module`
			A complete description of the gateware behaviour required.
		"""
		m = Module()
		rom, descriptorMaxLength, maxVendorCode = self.generateROM()
		m.submodules.readPort = readPort = rom.read_port(transparent = False)

		romLowerHalf = readPort.data.word_select(0, 16)
		romUpperHalf = readPort.data.word_select(1, 16)
		romElementPointer = romLowerHalf.bit_select(2, readPort.addr.width)
		romElementCount = romUpperHalf
		vendorCode = Signal.like(self.request)
		length = Signal(16)

		wordsRemaining = self.length - self.startPosition
		with m.If(wordsRemaining <= self._maxPacketLength):
			m.d.sync += length.eq(wordsRemaining)
		with m.Else():
			m.d.sync += length.eq(self._maxPacketLength)

		m.d.sync += vendorCode.eq(self.request - 1)

		positionInStream = Signal(range(descriptorMaxLength))
		bytesSent = Signal.like(length)

		descriptorLength = Signal.like(length)
		descriptorDataBaseAddress = Signal(readPort.addr.width)

		onFirstPacket = positionInStream == self.startPosition
		onLastPacket = (
			(positionInStream == descriptorLength - 1) |
			(bytesSent + 1 >= length)
		)

		with m.FSM():
			with m.State('IDLE'):
				m.d.sync += bytesSent.eq(0)
				m.d.comb += readPort.addr.eq(0)
				with m.If(self.start):
					m.next = 'START'

			with m.State('START'):
				m.d.comb += readPort.addr.eq(vendorCode)
				m.d.sync += positionInStream.eq(self.startPosition)
				isValidSet = vendorCode < maxVendorCode
				with m.If(isValidSet):
					m.next = 'LOOKUP_DESCRIPTOR'
				with m.Else():
					m.d.comb += self.stall.eq(1)
					m.next = 'IDLE'

			with m.State('LOOKUP_DESCRIPTOR'):
				m.d.comb += readPort.addr.eq((romLowerHalf + positionInStream).bit_select(2, readPort.addr.width))
				m.d.sync += [
					descriptorDataBaseAddress.eq(romElementPointer),
					descriptorLength.eq(romElementCount),
				]
				m.next = 'SEND_DESCRIPTOR'

			with m.State('SEND_DESCRIPTOR'):
				wordInStream = positionInStream.shift_right(2)
				byteInStream = positionInStream.bit_select(0, 2)

				m.d.comb += [
					self.tx.valid.eq(1),
					readPort.addr.eq(descriptorDataBaseAddress + wordInStream),
					self.tx.payload.eq(readPort.data.word_select(~byteInStream, 8)),
					self.tx.first.eq(onFirstPacket),
					self.tx.last.eq(onLastPacket),
				]

				with m.If(self.tx.ready):
					with m.If(~onLastPacket):
						m.d.sync += [
							positionInStream.eq(positionInStream + 1),
							bytesSent.eq(bytesSent + 1),
						]
						m.d.comb += readPort.addr.eq(descriptorDataBaseAddress +
							(positionInStream + 1).bit_select(2, positionInStream.width - 2)),
					with m.Else():
						m.d.sync += [
							descriptorLength.eq(0),
							descriptorDataBaseAddress.eq(0),
						]
						m.next = 'IDLE'

		if self._domain != 'sync':
			m = DomainRenamer({'sync': self._domain})(m)
		return m
