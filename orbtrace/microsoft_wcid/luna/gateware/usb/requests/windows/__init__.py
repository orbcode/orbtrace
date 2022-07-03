# SPDX-License-Identifier: BSD-3-Clause
from amaranth import Module, Signal
from usb_protocol.types import USBRequestType, USBRequestRecipient
from ......usb_protocol.types.descriptors.microsoft import MicrosoftRequests
from ......usb_protocol.emitters.descriptors.microsoft import PlatformDescriptorCollection
from luna.gateware.usb.usb2.request import USBRequestHandler, SetupPacket

from .descriptorSet import GetDescriptorSetHandler

__all__ = (
	'WindowsRequestHandler',
)

class WindowsRequestHandler(USBRequestHandler):
	""" The platform-specific handler for Windows requests.

	Parameters
	----------
	descriptors
		A collection of the platform-specific descriptors to respond to Windows with as requested.
	maxPacketSize
		The size of the largest allowable packet configured on endpoint 0.

	Notes
	-----
	The handler operates by reacting to incoming setup packets targeted directly to the device with the
	request type set to vendor-specific. It handles this and responds in accordance with the
	`Microsoft OS 2.0 Descriptors Specification <https://docs.microsoft.com/en-us/windows-hardware/drivers/usbcon/microsoft-os-2-0-descriptors-specification>`_.

	The main thing this handler has to deal with are the vendor requests to the device as the
	:py:class:`usb_protocol.emitters.descriptors.microsoft.PlatformDescriptorCollection` and
	descriptor system deals with the the rest of the spec.

	To this end, when triggered, the handler works as follows:

	* The state machine does switches from :code:`IDLE` into the :code:`CHECK_GET_DESCRIPTOR_SET` state,
	* In the following cycle, we validate the request parameters and if they check out
	  we enter the :code:`GET_DESCRIPTOR_SET` state,
	* In the :code:`GET_DESCRIPTOR_SET` state, when the data phase begins, we set our instance of the
	  :py:class:`dragonBoot.windows.descriptorSet.GetDescriptorSetHandler` running,
	* While the requested descriptor has not yet been delivered in full, we track data phase acks and:

		* When each complete packet is acked, update state in the
		  :py:class:`dragonBoot.windows.descriptorSet.GetDescriptorSetHandler` to keep the data flowing.
		* Keep the transmit :code:`DATA0`/:code:`DATA1` packet ID value correct.

	* Once the data phase concludes and the status phase begins, we then respond to the host with an all-clear ACK
	* If either the :py:class:`dragonBoot.windows.descriptorSet.GetDescriptorSetHandler` or the status phase
	  concludes, we return to :code:`IDLE`.
	"""
	def __init__(self, descriptors : PlatformDescriptorCollection, maxPacketSize = 64):
		self.descriptors = descriptors
		self._maxPacketSize = maxPacketSize

		super().__init__()

	def elaborate(self, platform) -> Module:
		""" Describes the specific gateware needed to implement the platform-specific windows descriptor handling on USB EP0.

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
		interface = self.interface
		setup = interface.setup
		tx = interface.tx

		m.submodules.getDescriptorSet = descriptorSetHandler = GetDescriptorSetHandler(self.descriptors)
		m.d.comb += [
			descriptorSetHandler.request.eq(setup.request),
			descriptorSetHandler.length.eq(setup.length),
		]

		with m.If(self.handlerCondition(setup)):
			with m.FSM(domain = 'usb'):
				# IDLE -- not handling any active request
				with m.State('IDLE'):
					# If we've received a new setup packet, handle it.
					with m.If(setup.received):
						with m.Switch(setup.index):
							with m.Case(MicrosoftRequests.GET_DESCRIPTOR_SET):
								m.d.usb += [
									# Start at the beginning of our next / fresh GET_DESCRIPTOR request.
									descriptorSetHandler.startPosition.eq(0),
									# Always start our responses with DATA1 pids, per [USB 2.0: 8.5.3].
									self.interface.tx_data_pid.eq(1)
								]
								m.next = 'CHECK_GET_DESCRIPTOR_SET'
							with m.Default():
								m.next = 'UNHANDLED'

				# CHECK_GET_DESCRIPTOR_SET -- Validate a platform-specific descriptor set request
				with m.State('CHECK_GET_DESCRIPTOR_SET'):
					with m.If(setup.is_in_request & (setup.value == 0)):
						m.next = 'GET_DESCRIPTOR_SET'
					with m.Else():
						m.next = 'UNHANDLED'

				# GET_DESCRIPTOR_SET -- The host is trying to request a platform-specific descriptor set
				with m.State('GET_DESCRIPTOR_SET'):
					expectingAck = Signal()

					m.d.comb += [
						descriptorSetHandler.tx.attach(tx),
						interface.handshakes_out.stall.eq(descriptorSetHandler.stall),
					]

					with m.If(interface.data_requested):
						m.d.comb += descriptorSetHandler.start.eq(1)
						m.d.usb += expectingAck.eq(1)

					with m.If(interface.handshakes_in.ack & expectingAck):
						nextStartPosition = descriptorSetHandler.startPosition + self._maxPacketSize
						m.d.usb += [
							descriptorSetHandler.startPosition.eq(nextStartPosition),
							self.interface.tx_data_pid.eq(~self.interface.tx_data_pid),
							expectingAck.eq(0),
						]

					with m.If(interface.status_requested):
						m.d.comb += interface.handshakes_out.ack.eq(1)
						m.next = 'IDLE'
					with m.Elif(descriptorSetHandler.stall):
						m.next = 'IDLE'

				# UNHANDLED -- we've received a request we're not prepared to handle
				with m.State('UNHANDLED'):
					# Wen we next have an opportunity to stall, do so and then return to idle.
					with m.If(interface.data_requested | interface.status_requested):
						m.d.comb += interface.handshakes_out.stall.eq(1)
						m.next = 'IDLE'

		return m

	def handlerCondition(self, setup : SetupPacket):
		""" Defines the setup packet conditions under which the request handler will operate.

		This is used to gate the handler's operation and forms part of the condition under which
		the stall-only handler in :py:class:`dragonBoot.bootloader.DragonBoot` will be triggered.

		Parameters
		----------
		setup
			A grouping of signals used to describe the most recent setup packet the control interface has seen.

		Returns
		-------
		:py:class:`amranth.hdl.ast.Operator`
			A combinatorial operation defining the sum conditions under which this handler will operate.

		Notes
		-----
		The condition for the operation of this handler is defined as being:

		* A Vendor request directly to the device.
		* for either index value 0x07 or 0x08, respectively meaning:

			* :code:`GET_DESCRIPTOR_SET`, and
			* :code:`SET_ALTERNATE_ENUM`

		The latter has not been given support as we don't currently allow swapping out the device
		descriptors in this manner.
		"""
		return (
			(setup.type == USBRequestType.VENDOR) &
			(setup.recipient == USBRequestRecipient.DEVICE) &
			(
				(setup.index == MicrosoftRequests.GET_DESCRIPTOR_SET) |
				(setup.index == MicrosoftRequests.SET_ALTERNATE_ENUM)
			)
		)
