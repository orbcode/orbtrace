from amaranth                import *
from .dbgIF                  import DBGIF

# Principle of operation
# ======================
#
# This module takes frames from the stream handler, parses them and sends them to the dbgif below for
# processing. In general this layer avoids doing any manipulation of the line, that is all handled
# below, with the intention of being able to replace cmsis-dap with another dap controller if
# needed.
#
# Communication with the dbgif is via a register and flag mechanism. Registers are filled with the
# appropriate information, then 'go' is set. When the dbgif accepts the command it drops 'done'
# and this layer can then release 'go'. When the command finishes 'done' is set true again.
#
# Default configuration information
# =================================

DAP_CONNECT_DEFAULT      = 1                # Default connect is SWD
DAP_PROTOCOL_STRING_LEN  = 5
DAP_PROTOCOL_STRING      = Cat(C(DAP_PROTOCOL_STRING_LEN+1,8),C(ord('2'),8),C(ord('.'),8),C(ord('1'),8),C(ord('.'),8),C(ord('0'),8),C(0,8)) # Protocol version V2.1.0
DAP_VERSION_STRING_LEN   = 4
DAP_VERSION_STRING       = Cat(C(DAP_VERSION_STRING_LEN+1,8),C(0x31,8),C(0x2e,8),C(0x30,8),C(0x30,8),C(0,8))
DAP_CAPABILITIES         = 0x03             # JTAG and SWD Debug
DAP_TD_TIMER_FREQ        = 0x3B9ACA00       # 1uS resolution timer
DAP_MAX_PACKET_COUNT     = 1                # 1 max packet count
DAP_V1_MAX_PACKET_SIZE   = 64
DAP_V2_MAX_PACKET_SIZE   = 508
MAX_MSG_LEN              = DAP_V2_MAX_PACKET_SIZE

# CMSIS-DAP Protocol Messages
# ===========================

DAP_Info                 = 0x00
DAP_HostStatus           = 0x01
DAP_Connect              = 0x02
DAP_Disconnect           = 0x03
DAP_TransferConfigure    = 0x04
DAP_Transfer             = 0x05
DAP_TransferBlock        = 0x06
DAP_TransferAbort        = 0x07
DAP_WriteABORT           = 0x08
DAP_Delay                = 0x09
DAP_ResetTarget          = 0x0a
DAP_SWJ_Pins             = 0x10
DAP_SWJ_Clock            = 0x11
DAP_SWJ_Sequence         = 0x12
DAP_SWD_Configure        = 0x13
DAP_JTAG_Sequence        = 0x14
DAP_JTAG_Configure       = 0x15
DAP_JTAG_IDCODE          = 0x16
DAP_SWO_Transport        = 0x17
DAP_SWO_Mode             = 0x18
DAP_SWO_Baudrate         = 0x19
DAP_SWO_Control          = 0x1a
DAP_SWO_Status           = 0x1b
DAP_SWO_Data             = 0x1c
DAP_SWD_Sequence         = 0x1d
DAP_SWO_ExtendedStatus   = 0x1e
DAP_ExecuteCommands      = 0x7f

DAP_QueueCommands        = 0x7e
DAP_Invalid              = 0xff

# Commands to the dbgIF
# =====================

CMD_RESET                = 0
CMD_PINS_WRITE           = 1
CMD_TRANSACT             = 2
CMD_SET_SWD              = 3
CMD_SET_JTAG             = 4
CMD_SET_SWJ              = 5
CMD_SET_JTAG_CFG         = 6
CMD_SET_CLK              = 7
CMD_SET_SWD_CFG          = 8
CMD_WAIT                 = 9
CMD_CLR_ERR              = 10
CMD_SET_RST_TMR          = 11
CMD_SET_TFR_CFG          = 12
CMD_JTAG_GET_ID          = 13
CMD_JTAG_RESET           = 14

# dbgIF ACK Codes
# ===============
ACK_OK                   = 1
ACK_WAIT                 = 2
ACK_ERROR                = 4

# TODO/Done
# =========

# DAP_Info               : Done
# DAP_Hoststatus         : Done (But not tied to h/w)
# DAP_Connect            : Done
# DAP_Disconnect         : Done
# DAP_WriteABORT         : Done
# DAP_Delay              : Done
# DAP_ResetTarget        : Done
# DAP_SWJ_Pins           : Done
# DAP_SWJ_Clock          : Done
# DAP_SWJ_Sequence       : Done
# DAP_SWD_Configure      : Done
# DAP_SWD_Sequence       : Done
# DAP_SWO_Transport      : Not implemented (indicated in config bits)
# DAP_SWO_Mode           : Not implemented (indicated in config bits)
# DAP_SWO_Baudrate       : Not implemented (indicated in config bits)
# DAP_SWO_Control        : Not implemented (indicated in config bits)
# DAP_SWO_Status         : Not implemented (indicated in config bits)
# DAP_SWO_ExtendedStatus : Not implemented (indicated in config bits)
# DAP_SWO_Data           : Not implemented (indicated in config bits)
# DAP_JTAG_Sequence      : Done
# DAP_JTAG_Configure     : Done
# DAP_JTAG_IDCODE        : Done
# DAP_Transfer_Configure : Done
# DAP_Transfer           : Done (Masking & Match done, not tested)
# DAP_TransferBlock      : Done
# DAP_TransferAbort      : Done
# DAP_ExecuteCommands    : Not Implemented (indicated in config bits)
# DAP_QueueCommands      : Not Implemented (indicated in config bits)

# This is the RAM used to store responses before they are sent back to the host
# =============================================================================

class WideRam(Elaboratable):
    def __init__(self):
        self.adr   = Signal(range((MAX_MSG_LEN//4)))
        self.dat_r = Signal(32)
        self.dat_w = Signal(32)
        self.we    = Signal()
        self.mem   = Memory(width=32, depth=MAX_MSG_LEN//4)

    def elaborate(self, platform):
        m = Module()
        m.submodules.rdport = rdport = self.mem.read_port()
        m.submodules.wrport = wrport = self.mem.write_port()
        m.d.comb += [
            rdport.addr.eq(self.adr),
            wrport.addr.eq(self.adr),
            self.dat_r.eq(rdport.data),
            wrport.data.eq(self.dat_w),
            wrport.en.eq(self.we),
        ]
        return m

# This is the CMSIS-DAP handler itself
# ====================================

class CMSIS_DAP(Elaboratable):
    def __init__(self, streamIn, streamOut, dbgif, v2Indication):
        # External interface (generally LEDs)
        self.running        = Signal()       # Flag for if target is running
        self.connected      = Signal()       # Flag for if target is connected
        self.can            = Signal()       # Canary

        # Nature of the USB connection
        self.isV2           = v2Indication
        self.streamIn       = streamIn
        self.streamOut      = streamOut

        # Receive block construction
        self.rxBlock        = Signal( 7*8 )  # Longest message we pickup is 6 bytes + command
        self.rxLen          = Signal(3)      # Rxlen to pick up
        self.rxedLen        = Signal(3)      # Rxlen picked up so far

        # Transmit block construction
        self.txBlock        = Signal( 14*8 ) # Response to be returned
        self.txLen          = Signal(range(MAX_MSG_LEN))     # Length of response to be returned
        self.txedLen        = Signal(range(MAX_MSG_LEN))     # Length of response that has been returned so far
        self.busy           = Signal()       # Indicator that we can't receive stream traffic at the moment

        # Support for block transfer mechanism
        self.tfr_txb        = Signal(4)      # TFR State machine index (12 states)

        # Support for SWJ_Sequence
        self.transferSCount = Signal(8)      # Number of transfers
        self.swj_txb        = Signal(2)      # SWJ State machine index (4 states)
        self.swjbcount      = Signal(3)      # Swjbcount in transmission sequence

        # Support for Sequence (Covers both JTAG and SWD cases)
        self.seq_txb        = Signal(4)      # SWD State machine index (9 states)
        self.seqOut         = Signal(8)      # Data to go out
        self.seqIn          = Signal(8)      # Data to come in
        self.seqPendingTX   = Signal(8)      # Data to be sent out
        self.seqckCycles    = Signal(6)      # Number of TCK cycles
        self.seqIsRead      = Signal()       # Flag indicating this a read
        self.bitCount       = Signal(3)      # Bits of the byte going in or out (we rely on the wrap, so 3 bits)
        self.seqCount       = Signal(8)      # Number of sequences that follow

        # Support for JTAG_Configure
        self.jtag_ircount   = Signal(5)      # Count of bits for IR devices in chain
        self.isJTAG         = Signal()       # Indicator that this is JTAG and not SWD

        # Support for DAP_Transfer
        self.transferTCount = Signal(8)      # Number of transfers
        self.mask           = Signal(32)     # Match mask register
        self.retries        = Signal(16)     # Retry counter for WAIT
        self.matchretries   = Signal(16)     # Retry counter for Value Matching
        self.tfrReq         = Signal(8)      # Transfer request from controller
        self.tfrData        = Signal(32)     # Transfer data from controller
        self.readAgain      = Signal()       # Need an extra swd read to collect valid data
        self.readDelay      = Signal()       # We are doing a posted read
        self.readIgnore     = Signal()       # Don't swallow this data, we're starting to post
        self.PendPayload    = Signal(8)      # Delayed command as a result of coming out of post

        # Support for DAP_Transfer_Block
        self.tfB_txb        = Signal(4)      # TFR Block State machine index (12 states)
        self.Bretries       = Signal(16)     # Retry counter for WAIT        
        self.transferBCount = Signal(16)     # Number of transfers 1..65535
        self.readBDelay     = Signal()       # We are doing a posted read
        self.readBIgnore    = Signal()       # Don't swallow this data, we're starting to post

        # Support for RESP_Transfer_Complete
        self.txb            = Signal(4)      # Transfer complete state machine (8 states)
        self.transferCCount = Signal(16)     # Number of transfers 1..65535
        
        # CMSIS-DAP Configuration info
        self.waitRetry      = Signal(16,reset=4096) # Number of transfer retries after WAIT response
        self.matchRetry     = Signal(16,reset=16)   # Number of retries on reads with Value Match in DAP_Transfer

        self.dbgif      = dbgif

    # ----------------------------------------------------------------------------------
    def RESP_Invalid(self, m):
        # Simply transmit an 'invalid' packet back
        m.d.sync += [
            self.txBlock.word_select(0,8).eq(C(DAP_Invalid,8)),
            self.txLen.eq(1)
        ]
        m.next = 'RESPOND'
    # ----------------------------------------------------------------------------------
    def RESP_Info(self, m):
        # <b:0x00> <b:requestId>
        # Transmit requested information packet back
        m.next = 'RESPOND'

        with m.Switch(self.rxBlock.word_select(1,8)):
            # These cases are not implemented in this gateware
            # Get the Vendor ID, Product ID, Serial Number, Target Device Vendor, Target Device Name,
            # Target Board Vendor, Target Board Name
            with m.Case(0x01, 0x02, 0x03, 0x05, 0x06, 0x07, 0x08):
                m.d.sync += [ self.txLen.eq(2), self.txBlock[8:16].eq(Cat(C(0,8))) ]
            with m.Case(0x04): # Get the CMSIS-DAP Firmware Version (string)
                m.d.sync += [ self.txLen.eq(3+DAP_PROTOCOL_STRING_LEN),
                              self.txBlock.bit_select(8,8+(2+DAP_PROTOCOL_STRING_LEN)*8).eq(DAP_PROTOCOL_STRING) ]
            with m.Case(0x09): # Get the Product Firmware version (string)
                m.d.sync += [ self.txLen.eq(3+DAP_VERSION_STRING_LEN),
                              self.txBlock.bit_select(8,8+(2+DAP_VERSION_STRING_LEN)*8).eq(DAP_VERSION_STRING)  ]
            with m.Case(0xF0): # Get information about the Capabilities (BYTE) of the Debug Unit
                m.d.sync+=[self.txLen.eq(3), self.txBlock[8:24].eq(Cat(C(1,8),C(DAP_CAPABILITIES,8)))]
            with m.Case(0xF1): # Get the Test Domain Timer parameter information
                m.d.sync+=[self.txLen.eq(6), self.txBlock[8:56].eq(Cat(C(8,8),C(DAP_TD_TIMER_FREQ,32)))]
            with m.Case(0xFE): # Get the maximum Packet Count (BYTE)
                m.d.sync+=[self.txLen.eq(6), self.txBlock[8:24].eq(Cat(C(1,8),C(DAP_MAX_PACKET_COUNT,8)))]
            with m.Case(0xFF): # Get the maximum Packet Size (SHORT).
                with m.If(self.isV2):
                    m.d.sync+=[self.txLen.eq(6), self.txBlock[8:32].eq(Cat(C(2,8),C(DAP_V2_MAX_PACKET_SIZE,16)))]
                with m.Else():
                    m.d.sync+=[self.txLen.eq(6), self.txBlock[8:32].eq(Cat(C(2,8),C(DAP_V1_MAX_PACKET_SIZE,16)))]
            with m.Default():
                m.next = 'Error'
    # ----------------------------------------------------------------------------------
    def RESP_Not_Implemented(self, m):
        m.d.sync += self.txBlock[8:16].eq(C(0xff,8))
        m.next = 'RESPOND'
    # ----------------------------------------------------------------------------------
    def RESP_HostStatus(self, m):
        # <b:0x01> <b:type> <b:status>
        # Set LEDs for condition of debugger
        m.next = 'RESPOND'

        with m.Switch(self.rxBlock.word_select(1,8)):
            with m.Case(0x00): # Connect LED
                m.d.sync+=self.connected.eq(self.rxBlock.word_select(2,8)==C(1,8))
            with m.Case(0x01): # Running LED
                m.d.sync+=self.running.eq(self.rxBlock.word_select(2,8)==C(1,8))
            with m.Default():
                m.next = 'Error'
    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------
    def RESP_Connect_Setup(self, m):
        # <b:0x02> <b:Port>
        # Perform connect operation
        m.next = 'Error'

        if (DAP_CAPABILITIES&(1<<0)):
            # SWD mode is permitted
            with m.If ((((self.rxBlock.word_select(1,8))==0) & (DAP_CONNECT_DEFAULT==1)) |
                       ((self.rxBlock.word_select(1,8))==1)):
                m.d.sync += [
                    self.txBlock.word_select(0,16).eq(Cat(self.rxBlock.word_select(0,8),C(1,8))),
                    self.dbgif.command.eq(CMD_SET_SWD),
                    self.isJTAG.eq(0),  
                    self.txLen.eq(2),
                    self.dbgif.go.eq(1)
                    ]
                m.next = 'DAP_Wait_Connect_Done'

        if (DAP_CAPABILITIES&(1<<1)):
            with m.If ((((self.rxBlock.word_select(1,8))==0) & (DAP_CONNECT_DEFAULT==2)) |
                       ((self.rxBlock.word_select(1,8))==2)):
                m.d.sync += [
                    self.txBlock.word_select(0,16).eq(Cat(self.rxBlock.word_select(0,8),C(2,8))),
                    self.dbgif.command.eq(CMD_SET_JTAG),
                    self.isJTAG.eq(1),                    
                    self.txLen.eq(2),
                    self.dbgif.go.eq(1)
                    ]
                m.next = 'DAP_Wait_Connect_Done'

    def RESP_Wait_Connect_Done(self, m):
        # Generic wait for inferior to process command
        with m.If((self.dbgif.go==1) & (self.dbg_done==0)):
            m.d.sync+=self.dbgif.go.eq(0)
        with m.If((self.dbgif.go==0) & (self.dbg_done==1)):
            m.next='RESPOND'
    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------
    def RESP_Wait_Done(self, m):
        # Generic wait for inferior to process command
        with m.If((self.dbgif.go==1) & (self.dbg_done==0)):
            m.d.sync+=self.dbgif.go.eq(0)
        with m.If((self.dbgif.go==0) & (self.dbg_done==1)):
            m.d.sync += self.txBlock.bit_select(8,8).eq(Mux(self.dbgif.perr,0xff,0))
            m.next='RESPOND'
    # ----------------------------------------------------------------------------------
    def RESP_Disconnect(self, m):
        # <b:0x03>
        # Perform disconnect
        m.d.sync += [
            self.running.eq(0),
            self.connected.eq(0),
            self.isJTAG.eq(1),
        ]
        m.next = 'RESPOND'
    # ----------------------------------------------------------------------------------
    def RESP_WriteABORT(self, m):
        # <b:0x08> <b:DapIndex> <w:AbortCode>
        # Post abort code to register
        # TODO: Add ABORT for JTAG
        m.d.sync += [
            self.dbgif.command.eq(CMD_TRANSACT),
            self.dbgif.apndp.eq(0),
            self.dbgif.rnw.eq(0),
            self.dbgif.addr32.eq(0),
            self.dbgif.dwrite.eq(self.rxBlock.bit_select(16,32)),
            self.dbgif.go.eq(1)
        ]

        m.next='DAP_Wait_Done'
    # ----------------------------------------------------------------------------------
    def RESP_Delay(self, m):
        # <b:0x09> <s:Delay>
        # Delay for programmed number of uS
        m.d.sync += [
            self.dbgif.dwrite.eq( Cat(self.rxBlock.bit_select(8,16), C(0,16))),
            self.dbgif.command.eq( CMD_WAIT ),
            self.dbgif.go.eq(1)
        ]
        m.next='DAP_Wait_Done'
    # ----------------------------------------------------------------------------------
    def RESP_ResetTarget(self, m):
        # <b:0x0A>
        # Reset the target
        m.d.sync += [
            self.txBlock.bit_select(8,16).eq(C(0,16)),
            self.txLen.eq(3),
            self.dbgif.command.eq( CMD_RESET ),
            self.dbgif.go.eq(1)
        ]
        m.next='DAP_Wait_Done'
    # ----------------------------------------------------------------------------------
    def RESP_SWJ_Pins_Setup(self, m):
        # <b:0x10> <b:PinOutput> <b:PinSelect> <w:PinWait>
        # Control and monitor SWJ/JTAG pins
        m.d.sync += [
            self.dbgif.pinsin.eq( self.rxBlock.bit_select(8,16) ),
            self.dbgif.dwrite.eq( self.rxBlock.bit_select(24,32) ),
            self.dbgif.command.eq( CMD_PINS_WRITE ),
            self.dbgif.go.eq(1)
            ]
        m.next = 'DAP_SWJ_Pins_PROCESS';

    def RESP_SWJ_Pins_Process(self, m):
        # Spin waiting for debug interface to do its thing
        with m.If((self.dbgif.go==1) & (self.dbg_done==0)):
            m.d.sync+=self.dbgif.go.eq(0)
        with m.If((self.dbgif.go==0) & (self.dbg_done==1)):
            m.d.sync+=self.txBlock.word_select(1,8).eq(self.dbgif.pinsout)
            m.next='RESPOND'

    # ----------------------------------------------------------------------------------
    def RESP_SWJ_Clock(self, m):
        # <0x11> <w:newclock>
        # Set clock frequency for JTAG and SWD comms
        m.d.sync += [
            self.dbgif.dwrite.eq( self.rxBlock.bit_select(8,32) ),
            self.dbgif.command.eq( CMD_SET_CLK ),
            self.dbgif.go.eq(1)
            ]
        m.next='DAP_Wait_Done'
    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------
    def RESP_SWJ_Sequence_Setup(self, m):
        # <b:0x12> <b:Count> [n x <bSeqDat>.....]
        # Generate SWJ Sequence data
        m.d.sync += [
            # Number of bits to be transferred
            self.transferSCount.eq(Mux(self.rxBlock.bit_select(8,8),Cat(self.rxBlock.bit_select(8,8),C(0,8)),C(256,16))),
            self.swj_txb.eq(0),

            # Setup to have control over swdo, swclk and swwr (set for output), with clocks of 1 clock cycle
            self.dbgif.dwrite.eq(0),
            self.dbgif.pinsin.eq(0b0000_0011_0001_0011),
            self.swjbcount.eq(0),
            self.dbgif.command.eq(CMD_PINS_WRITE)
            ]
        m.next = 'DAP_SWJ_Sequence_PROCESS'

    def RESP_SWJ_Sequence_Process(self, m):
        with m.Switch(self.swj_txb):
            # Grab next octet(s) from stream ------------------------------------------------------------
            with m.Case(0):
                with m.If(self.streamOut.valid & self.streamOut.ready):
                    m.d.sync += [
                        self.tfrData.eq(self.streamOut.payload),
                        self.swj_txb.eq(1)
                    ]
                with m.Else():
                    # If we're showing ~valid then this packet is foreshortened
                    with m.If(~self.streamOut.valid):
                        m.next = 'Error'
                    with m.Else():
                        m.d.sync += self.busy.eq(0)

            # Write the data bit -----------------------------------------------------------------------
            with m.Case(1):
                m.d.sync += [
                    self.dbgif.pinsin[1].eq(self.tfrData.bit_select(0,1)),
                    self.dbgif.pinsin[12].eq(1),
                    self.dbgif.pinsin[0].eq(0),
                    self.tfrData.eq(Cat(C(1,0),self.tfrData[1:8])),
                    self.transferSCount.eq(self.transferSCount-1),
                    self.dbgif.go.eq(1),
                    self.swjbcount.eq(self.swjbcount+1),
                    self.swj_txb.eq(2)
                ]

            # Wait for bit to be accepted, then we can drop clk ----------------------------------------
            with m.Case(2):
                with m.If(self.dbg_done==0):
                    m.d.sync += self.dbgif.go.eq(0)
                with m.If ((self.dbgif.go==0) & (self.dbg_done==1)):
                    m.d.sync += [
                        self.dbgif.pinsin[0].eq(1),
                        self.dbgif.go.eq(1),
                        self.swj_txb.eq(3)
                        ]

            # Now wait for clock to be complete, and move to next bit ----------------------------------
            with m.Case(3):
                with m.If(self.dbg_done==0):
                    m.d.sync += self.dbgif.go.eq(0)
                with m.If ((self.dbgif.go==0) & (self.dbg_done==1)):
                    with m.If(self.transferSCount!=0):
                        m.d.sync += self.swj_txb.eq(Mux(self.swjbcount,1,0))
                    with m.Else():
                        m.next = 'DAP_Wait_Done'

    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------
    def RESP_SWD_Configure(self, m):
        # <0x13> <ConfigByte>
        # Setup configuration for SWD
        m.d.sync += [
            self.dbgif.dwrite.eq( self.rxBlock.bit_select(8,8) ),
            self.dbgif.command.eq( CMD_SET_SWD_CFG ),
            self.dbgif.go.eq(1)
            ]
        m.next='DAP_Wait_Done'
    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------
    def RESP_JTAG_Configure_Setup(self, m):
        # <b:0x15> <b:Count> n x [ <b:IRLength> ]
        # Set IR Length for Chain

        m.d.sync += [
            self.dbgif.command.eq( CMD_SET_JTAG_CFG ),
            self.jtag_ircount.eq(0),
            self.dbgif.dev.eq(self.rxBlock.bit_select(8,3)-1)
            ]
        m.next='JTAG_Configure_PROCESS';

    def RESP_JTAG_Configure_Process(self, m):
        # Collect octets representing the irlength for each member of the chain
        with m.If(self.streamOut.valid & self.streamOut.ready):
            m.d.sync += [
                self.dbgif.dwrite.bit_select( self.jtag_ircount,5 ).eq(self.streamOut.payload.bit_select(0,5)),
                self.jtag_ircount.eq(self.jtag_ircount+5)
            ]
            with m.If(self.streamOut.last):
                m.d.sync += self.dbgif.go.eq(1)
                m.next = 'DAP_Wait_Done'
        with m.Else():
            # If we're showing ~valid then this packet is foreshortened
            with m.If(~self.streamOut.valid):
                m.next = 'Error'
            with m.Else():
                m.d.sync += self.busy.eq(0)

    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------
    def RESP_JTAG_IDCODE_Setup(self, m):
        # <b:0x16> <b:JTAGIndex>
        # Request ID code for specified device
        m.d.sync += [
            self.dbgif.command.eq(CMD_JTAG_GET_ID),
            self.dbgif.dwrite.eq( self.rxBlock.bit_select(8,8) ),
            self.txLen.eq(6),
            self.txBlock.bit_select(16,32).eq(0),
            self.dbgif.go.eq(1)
            ]

        m.next = 'JTAG_IDCODE_Process'

    def RESP_JTAG_IDCODE_Process(self, m):
        with m.If(self.dbg_done==0):
            m.d.sync += self.dbgif.go.eq(0)
        with m.Elif(self.dbg_done==1):
            m.d.sync += self.txBlock.bit_select(16,32).eq(self.dbgif.dread)
            m.next = "RESPOND"

    # ----------------------------------------------------------------------------------
    def RESP_TransferConfigure(self, m):
        # <b:0x04> <b:IdleCycles> <s:WaitRetry> <s:MatchRetry>
        # Configure transfer parameters
        m.d.sync += [
            self.waitRetry.eq(self.rxBlock.bit_select(16,16)),
            self.matchRetry.eq(self.rxBlock.bit_select(32,16)),

            # Send idleCycles to layers below
            self.dbgif.dwrite.eq(self.rxBlock.bit_select(8,8)),
            self.dbgif.command.eq(CMD_SET_TFR_CFG),
            self.dbgif.go.eq(1)
        ]

        m.next = 'DAP_Wait_Done'
    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------
    def RESP_Transfer_Setup(self, m):
        # <0x05> <b:DapIndex> <b:TfrCount] n x [ <b:TfrReq> <opt w:TfrData>]
        # Triggered at start of a Transfer data sequence
        # We have the command, index and transfer count, need to set up to get the transfers

        m.d.sync += [
            self.dbgif.dev.eq(self.rxBlock.bit_select(8,3)),
            self.transferTCount.eq(self.rxBlock.bit_select(16,8)),
            self.tfrram.adr.eq(0),
            self.tfr_txb.eq(0),
            self.readAgain.eq(0),
            self.readDelay.eq(0),
            self.readIgnore.eq(0),

            # Ensure any subsequent block read starts from scratch
            self.readBDelay.eq(0)
        ]

        # Filter for case someone tries to send us no transfers to perform
        # in which case we send back a good ack!
        with m.If(self.rxBlock.bit_select(16,8)!=0):
            m.next = 'DAP_Transfer_PROCESS';
        with m.Else():
            m.d.sync += [
                self.txBlock.word_select(2,8).eq(C(1,8)),
                self.txLen.eq(3)
                ]
            m.next = 'RESPOND'

                
    def RESP_Transfer_Process(self, m):
        m.d.comb += self.tfrram.dat_w.eq(self.dbgif.dread)

        with m.Switch(self.tfr_txb):
            # Get transfer request from stream, or the previous one if the post is finishing ----------
            with m.Case(0):
                m.d.sync += [
                    self.retries.eq(self.waitRetry),
                    self.matchretries.eq(self.matchRetry)
                    ]
                with m.If(self.readAgain):
                    m.d.sync += [
                        self.readAgain.eq(0),
                        # Use the old payload we got
                        self.tfrReq.eq(self.PendPayload),
                        self.tfr_txb.eq(1)
                    ]
                with m.Elif(self.transferTCount==0):
                    # No more transfers to be performed. If there's a posted transfer in progress then
                    # deal with that, otherwise go to post the reply
                    with m.If(self.readDelay):
                        # This is an end-of-post, so we need to do a read from RDBUFF
                        m.d.sync += [
                            self.tfr_txb.eq(6),
                            self.tfrReq.eq(0x0e),
                            self.readDelay.eq(0),                    
                        ]
                    with m.Else():
                        # Otherwise progress to the exit states
                        m.d.sync += self.tfr_txb.eq(10)

                with m.Else():
                    with m.If(~(self.streamOut.valid & self.streamOut.ready)):
                        # If we're showing ~valid then this packet is foreshortened
                        with m.If(~self.streamOut.valid):
                            m.next = 'Error'
                        with m.Else():
                            m.d.sync += self.busy.eq(0)
                    with m.Else():
                        # We are consuming this event, so count it
                        with m.If(self.transferTCount):
                            m.d.sync += self.transferTCount.eq(self.transferTCount-1)
                        # This is a good transaction from the stream, so record the fact it's in flow
                        m.d.sync += self.txBlock.word_select(1,8).eq(self.txBlock.word_select(1,8)+1)
                    
                        # Check to see if readDelay continues...
                        # Rule for JTAG is any read, for SWD it's any AP read
                        # If it doesn't then we need to collect these data before progressing
                        with m.If(self.readDelay &
                                   ((self.isJTAG & (~self.streamOut.payload.bit_select(1,1))) |
                                    (~self.isJTAG & (self.streamOut.payload.bit_select(0,2)!=3)))):
                            m.d.sync += [
                                self.tfr_txb.eq(6),
                                self.tfrReq.eq(0x0e),
                                self.readDelay.eq(0),
                                self.readAgain.eq(1),
                                self.PendPayload.eq(self.streamOut.payload),
                                ]
                        with m.Else():
                            m.d.sync += [
                                self.tfrReq.eq(self.streamOut.payload),
                                self.tfr_txb.eq(1)
                            ]

            with m.Case(1):
                # Calculate if this is the start of readDelay
                m.d.sync += [
                    self.readDelay.eq((self.isJTAG & (self.tfrReq.bit_select(1,1))) |
                                    ((~self.isJTAG) & (self.tfrReq.bit_select(0,2)==3))),
                    self.readIgnore.eq((~self.readDelay) & ((self.isJTAG & (self.tfrReq.bit_select(1,1))) |
                                                          ((~self.isJTAG) & (self.tfrReq.bit_select(0,2)==3))))
                    ]
                
                # ..and now go do the read or write as appropriate
                with m.If ((~self.tfrReq.bit_select(1,1)) |
                           self.tfrReq.bit_select(4,1) |
                           self.tfrReq.bit_select(5,1) ):                    
                    # Need to collect the value
                    m.d.sync += self.tfr_txb.eq(2)
                with m.Else():
                    # It's a read, no value to collect
                    m.d.sync += self.tfr_txb.eq(6)

            # Collect the 32 bit transfer Data to go with the command ----------------------------
            with m.Case(2,3,4,5):
                with m.If(self.streamOut.valid & self.streamOut.ready):
                    m.d.sync+=[
                        # Beware, state used to select byte in word construction
                        self.tfrData.word_select(self.tfr_txb.bit_select(0,3)-2,8).eq(self.streamOut.payload),
                        self.tfr_txb.eq(self.tfr_txb+1)
                    ]

                    with m.If(self.tfrReq.bit_select(5,1) & (self.tfr_txb==6)):
                        # This is a match register write
                        m.d.sync += [
                            self.mask.eq(Cat(self.streamOut.payload,self.tfrData.bit_select(0,24))),
                            self.tfr_txb.eq(0)
                        ]
                with m.Else():
                    # If we're showing ~valid then this packet is foreshortened
                    with m.If(~self.streamOut.valid):
                        m.next = 'Error'
                    with m.Else():
                        m.d.sync +=self.busy.eq(0)

            # We have the command and any needed data, action it ---------------------------------------
            with m.Case(6):
                m.d.sync += [
                    self.dbgif.command.eq(CMD_TRANSACT),
                    self.dbgif.apndp.eq(self.tfrReq.bit_select(0,1)),
                    self.dbgif.rnw.eq(self.tfrReq.bit_select(1,1)),
                    self.dbgif.addr32.eq(self.tfrReq.bit_select(2,2)),
                    self.dbgif.dwrite.eq(self.tfrData),
                    self.dbgif.go.eq(1),
                    self.tfr_txb.eq(7),
                ]

            with m.Case(7): # We sent a command, wait for it to start being executed -----------------------------------
                with m.If(self.dbg_done==0):
                    m.d.sync+=[
                        self.dbgif.go.eq(0),
                        self.tfr_txb.eq(8)
                    ]

            # Wait for command to complete -------------------------------------------------------------
            with m.Case(8):
                with m.If(self.dbg_done==1):
                    # Write return value from this command into return frame
                    m.d.sync += self.txBlock.word_select(2,8).eq(Cat(self.dbgif.ack,self.dbgif.perr,C(0,4))),

                    # Now lets figure out how to handle this response....
                    # If we're to retry, then lets do it
                    with m.If(self.dbgif.ack==ACK_WAIT):
                        m.d.sync += [
                            self.retries.eq(self.retries-1),
                            self.tfr_txb.eq(Mux(self.retries!=0,6,10))
                        ]

                    # If we got a bad ACK then give up
                    with m.Elif((self.dbgif.ack!=ACK_OK) | (self.dbgif.perr)):
                        m.d.sync += self.tfr_txb.eq(10)

                    # Otherwise this one should be processed
                    with m.Else():
                        m.d.sync += self.tfr_txb.eq(9)

            # Good data reception, decide how to handle it -----------------------------------------------
            with m.Case(9):
                with m.If(self.tfrReq.bit_select(4,1)):
                    # This is a transfer match request
                    m.d.sync += self.matchretries.eq(self.matchretries-1)
                    with m.If(((self.dbgif.dread & self.mask) !=self.tfrData) & (self.matchretries==0)):
                        # Not a match and we've run out of attempts, so set bit 4
                        m.d.sync += self.txBlock.bit_select(21,1).eq(1)
                        m.d.sync += self.tfr_txb.eq(10)
                    with m.Else():
                        m.d.sync += self.tfr_txb.eq(6)

                with m.Else():
                    m.d.sync += self.readIgnore.eq(0)
                    with m.If((~self.readIgnore) & self.dbgif.rnw):
                        # We're instructed to record this...increment ram position
                        m.d.sync += self.tfrram.adr.eq(self.tfrram.adr+1)

                    m.d.sync += self.tfr_txb.eq(0)
                            
            # Transfer completed, start sending data back -----------------------------------------
            with m.Case(10,11,12):
                with m.If(self.streamIn.ready):
                    m.d.sync += [
                        self.streamIn.payload.eq(self.txBlock.word_select(self.tfr_txb-10,8)),
                        self.streamIn.valid.eq(1),
                        self.tfr_txb.eq(self.tfr_txb+1),
                        self.streamIn.last.eq(self.isV2 & (self.tfr_txb==12) & (self.tfrram.adr==0))
                    ]

            # Initial data sent, send any remaining material ------------------------------------------
            with m.Case(13):
                m.next = 'UPLOAD_RXED_DATA'
                m.d.sync += [
                    self.txb.eq(0),
                    self.txedLen.eq((self.tfrram.adr*4)+3)  # Record length of data to be returned
                ]
                
    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------
    def RESP_TransferBlock_Setup(self, m):
        # <B:0x06> <B:DapIndex> <S:TransferCount> <B:TransferReq> n x [ <W:TransferData> ])
        # Triggered at start of a TransferBlock data sequence
        # We have the command, index and transfer count, need to set up to get the transfers
        # Note that a posted read can stretch over multiple calls to this handler, so we have
        # to be careful to maintain posted status, (and reset it when any other call is done).

        m.d.sync += [
            # DAP Index is 1 byte in, transfer count is dealt with at the end
            self.dbgif.dev.eq(self.rxBlock.bit_select(13,3)),
            self.tfrram.adr.eq(0),

            # We will not read back the first word immediately if we're in JTAG read
            # or SWD read of the AP
            self.readBDelay.eq((self.isJTAG & self.rxBlock.bit_select(33,1)) |
                              ((~self.isJTAG) & (self.rxBlock.bit_select(32,2)==3))),

            # We only delay the first read if we weren't already in delay mode
            self.readBIgnore.eq((~self.readBDelay) &
                                ((self.isJTAG & self.rxBlock.bit_select(33,1)) |
                                 ((~self.isJTAG) & (self.rxBlock.bit_select(32,2)==3)))),

            self.dbgif.command.eq(CMD_TRANSACT),

            # Transfer Req is 4 bytes in
            self.dbgif.apndp.eq(self.rxBlock.bit_select(32,1)),
            self.dbgif.rnw.eq(self.rxBlock.bit_select(33,1)),
            self.dbgif.addr32.eq(self.rxBlock.bit_select(34,2)),

            # Reset the number of responses sent back
            self.txBlock.bit_select(8,16).eq(C(0,16)),
            self.Bretries.eq(self.waitRetry),

            # Decide which state to jump to depending on if we have data to collect
            self.tfB_txb.eq(Mux(self.rxBlock.bit_select(33,1),4,0))
        ]

        # Filter for case someone tries to send us no transfers to perform
        # in which case we send back a good ack!
        with m.If(self.rxBlock.bit_select(16,16)!=0):
            m.d.sync += self.transferBCount.eq(self.rxBlock.bit_select(16,16)-1)
            m.next = 'DAP_TransferBlock_PROCESS'
        with m.Else():
            m.d.sync += [
                self.txBlock.bit_select(24,8).eq(C(1,8)),
                self.txLen.eq(4)
            ]
            m.next = 'RESPOND'

    def RESP_TransferBlock_Process(self, m):
        m.d.comb += self.tfrram.dat_w.eq(self.dbgif.dread)

        with m.Switch(self.tfB_txb):

            # Collect the 32 bit transfer Data to go with the command ----------------------------------
            with m.Case(0,1,2,3):
                with m.If(self.streamOut.ready & self.streamOut.valid):
                    m.d.sync+=[
                        self.dbgif.dwrite.word_select(self.tfB_txb,8).eq(self.streamOut.payload),
                        self.tfB_txb.eq(self.tfB_txb+1),
                    ]
                with m.Else():
                    # If we're showing ~valid then this packet is foreshortened
                    with m.If(~self.streamOut.valid):
                        m.next = 'Error'
                    with m.Else():
                        m.d.sync +=self.busy.eq(0)

            # We have the command and any needed data, action it ---------------------------------------
            with m.Case(4):
                m.d.sync += [
                    self.dbgif.go.eq(1),
                    self.Bretries.eq(self.Bretries-1),
                    self.tfB_txb.eq(5)
                ]

            # Wait for command to be accepted ----------------------------------------------------------
            with m.Case(5):
                with m.If(~self.dbg_done):
                    m.d.sync += [
                        self.dbgif.go.eq(0),
                        self.tfB_txb.eq(6)
                        ]

            # We sent a command, wait for it to start being executed -----------------------------------
            with m.Case(6):
                with m.If(self.dbg_done==1):
                    # Write return value from this command into return frame
                    m.d.sync += self.txBlock.bit_select(24,8).eq(Cat(self.dbgif.ack,self.dbgif.perr,C(0,4))),

                    # Now lets figure out how to handle this response
                    # If we're to retry, then let's do it
                    with m.If(self.dbgif.ack==ACK_WAIT):
                        m.d.sync += self.tfB_txb.eq(Mux(self.Bretries!=0,4,8))

                    # If we got a bad ACK then give up
                    with m.Elif((self.dbgif.ack!=ACK_OK) | (self.dbgif.perr)):
                        m.d.sync += self.tfB_txb.eq(8)

                    with m.Else():
                        m.d.sync += self.readBIgnore.eq(0)
                        with m.If(~self.readBIgnore):
                            m.d.sync += self.transferBCount.eq(self.transferBCount-1)
                            m.d.sync += self.txBlock.bit_select(8,16).eq(self.txBlock.bit_select(8,16)+1)

                            # If this is something that resulted in data, then store the data
                            with m.If(self.dbgif.rnw):
                                m.d.sync += self.tfrram.adr.eq(self.tfrram.adr+1)

                        # Keep going if appropriate
                        with m.If((self.transferBCount!=0) | self.readBIgnore):
                            m.d.sync += [
                                self.Bretries.eq(self.waitRetry),
                                self.tfB_txb.eq(Mux(self.dbgif.rnw,4,0))
                            ]

                        with m.Else():
                            m.d.sync += self.tfB_txb.eq(8)

            # Transfer completed, start sending data back ---------------------------------------
            with m.Case(8,9,10,11):
                with m.If(self.streamIn.ready):
                    m.d.sync += [
                        # Beware, we use the bottom two bits of the state to select the byte to return
                        self.streamIn.payload.eq(self.txBlock.word_select(self.tfB_txb.bit_select(0,2),8)),
                        self.streamIn.valid.eq(1),
                        self.tfB_txb.eq(self.tfB_txb+1),
                        # End of transfer if there are no data to return
                        self.streamIn.last.eq(self.isV2 & (self.tfB_txb==11) & (self.dbgif.rnw==0))
                    ]

            # Initial data sent, decide what to do next ----------------------------------------------
            with m.Case(12):
                m.d.sync += [
                    self.txb.eq(0),
                    self.txedLen.eq((self.tfrram.adr*4)+4)  # Record length of data that will be returned
                ]
                m.next = 'UPLOAD_RXED_DATA'

    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------
                
    def RESP_Transfer_Complete(self, m):
        # Complete the process of returning data collected via either Transfer_Process or
        # TransferBlock_Process. Data count to be transferred is inferred by ram address and
        # the payload is in the tfrram.

        with m.Switch(self.txb):
            # Prepare transfer ------------------------------------------------------------------------
            with m.Case(0):
                m.d.sync += [
                    self.transferCCount.eq(self.tfrram.adr),
                    self.tfrram.adr.eq(0),
                ]

                with m.If(self.tfrram.adr!=0):
                    m.d.sync += self.txb.eq(1)
                with m.Else():
                    m.d.sync += self.txb.eq(7)

            # Wait for ram to propagate through -------------------------------------------------------
            with m.Case(1):
                m.d.sync += self.txb.eq(2)

            # Collect transfer value from RAM store ---------------------------------------------------
            with m.Case(2):
                m.d.sync += [
                    self.transferCCount.eq(self.transferCCount-1),
                    self.streamIn.payload.eq(self.tfrram.dat_r.word_select(0,8)),
                    self.txb.eq(3)
                ]

            # Send 32 bit value to outgoing stream -------------------------------------------
            with m.Case(3,4,5,6):
                m.d.sync += self.streamIn.valid.eq(1)
                with m.If(self.streamIn.ready & self.streamIn.valid):
                    m.d.sync += [
                        self.txb.eq(self.txb+1),
                        self.streamIn.payload.eq(self.tfrram.dat_r.word_select(self.txb-2,8)),
                        # 5 because of pipeline
                        self.streamIn.last.eq(self.isV2 & (~self.transferCCount.bool()) & (self.txb==5)),
                        self.streamIn.valid.eq(self.txb!=6)
                    ]

            # Finished this send ---------------------------------------------------------------------
            with m.Case(7):
                with m.If(self.streamIn.ready):
                    with m.If(~self.transferCCount.bool()):
                        with (m.If(self.isV2)):
                            m.next = 'IDLE'
                        with m.Else():
                            m.next = 'V1PACKETFILL'
                    with m.Else():
                        m.d.sync += [
                            self.txb.eq(1),
                            self.tfrram.adr.eq(self.tfrram.adr+1)
                        ]

    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------

    def RESP_Sequence_Setup(self, m):
        # <0x1D or 0x14> <SequenceCount> <SequenceInfo> ...
        # Generate SWD sequence and output on SWDIO or capture from SWDIO
        # or generate JTAG sequence on TCK, TMS, TDI with optional capture of TDO

        # Collect how many sequences we'll be processing, then move to get the first one
        m.d.sync += [
            self.seqCount.eq(self.rxBlock.word_select(1,8)),

            # Use the timing from the layer below
            self.dbgif.dwrite.eq(0),

            # In case this is CMSIS-DAP v1, keep a tally of whats been sent so we can pad the packet
            self.txedLen.eq(2),

            # For SWO we control swclk, swdio, swwr direction is set by request
            # For JTAG we control tms, tck, tdi, swwr set to output
            self.dbgif.pinsin.eq(Mux(self.isJTAG,0b0001_0111_0001_0001 , 0b0001_0011_0000_0001)),
            self.dbgif.command.eq(CMD_PINS_WRITE),
            self.seq_txb.eq(0)
        ]
        m.next = 'DAP_Sequence_PROCESS'

    def RESP_Sequence_PROCESS(self,m):
        m.d.sync += self.streamIn.valid.eq(0)

        with m.Switch(self.seq_txb):

            # -------------- # Send frontmatter
            with m.Case(0):
                with m.If(self.streamIn.ready):
                    m.d.sync += [
                        # Send frontmatter for reponse
                        self.streamIn.payload.eq(Mux(self.isJTAG,DAP_JTAG_Sequence,DAP_SWD_Sequence)),
                        self.streamIn.last.eq(0),
                        self.streamIn.valid.eq(1),

                        # This is the 'OK' that will be sent out next
                        self.seqPendingTX.eq(0),

                        # If there's nothing to be done then we are finished, otherwise start
                        self.seq_txb.eq(Mux(self.seqCount!=0,1,7))
                    ]

            # -------------- Next sequence, so Get info for it
            with m.Case(1):
                with m.If(self.streamOut.ready & self.streamOut.valid):
                    m.d.sync += [
                        self.seqCount.eq(self.seqCount-1),
                        self.seqckCycles.eq(self.streamOut.payload.bit_select(0,6)),

                        # If we're reading then we don't want to write to SWD, we do if it's JTAG (TMS)
                        self.dbgif.pinsin[4].eq(Mux(self.isJTAG,1,~self.streamOut.payload[7])),
                        self.seqIn.eq(0),

                        # Decide on correct state to move to and setup output for read or write condition
                        self.seqIsRead.eq(self.streamOut.payload[7]),
                        self.seq_txb.eq(Mux(self.isJTAG,2,Mux(self.streamOut.payload[7],3,2)))
                    ]
                    # If this is a JTAG sequence then set TMS
                    with m.If(self.isJTAG):
                        m.d.sync += self.dbgif.pinsin.bit_select(1,1).eq(self.streamOut.payload[6])
                with m.Else():
                    # If we're showing ~valid then this packet is foreshortened
                    with m.If(~self.streamOut.valid):
                        m.next = 'Error'
                    with m.Else():
                        m.d.sync += self.busy.eq(0)

            # -------------- We are writing SWO, or JTAG, so get byte of output data
            with m.Case(2):
                with m.If(self.streamOut.ready & self.streamOut.valid):
                    m.d.sync += [
                        self.seqOut.eq(self.streamOut.payload),
                        self.bitCount.eq(0),
                        self.seq_txb.eq(3)
                    ]
                with m.Else():
                    # If we're showing ~valid then this packet is foreshortened
                    with m.If(~self.streamOut.valid):
                        m.next = 'Error'
                    with m.Else():
                        m.d.sync += self.busy.eq(0)

            # -------------- Now output or input these data
            with m.Case(3):
                m.d.sync += [
                    # Send clock low
                    self.dbgif.pinsin.bit_select(0,1).eq(0),

                    self.seqckCycles.eq(self.seqckCycles-1),
                    self.dbgif.go.eq(1),
                    self.seq_txb.eq(4),
                    # Write to TDI if JTAG, SWDIO if SWD
                    self.dbgif.pinsin.bit_select(Mux(self.isJTAG,2,1),1).eq(self.seqOut.bit_select(self.bitCount,1))
                ]

            # ------------- Waiting until we can set TCK/SWCLK->1
            with m.Case(4):
                with m.If(self.dbg_done==0):
                    m.d.sync += self.dbgif.go.eq(0)
                with m.If ((self.dbgif.go==0) & (self.dbg_done==1)):
                    m.d.sync += [
                        # Bit is established, change the clock
                        self.dbgif.pinsin.bit_select(0,1).eq(1),
                        self.dbgif.go.eq(1),
                        self.seq_txb.eq(5)
                    ]

            # ------------- Sent this bit, waiting for clock 1 to complete
            with m.Case(5):
                with m.If(self.dbg_done==0):
                    m.d.sync += self.dbgif.go.eq(0)
                with m.If ((self.dbgif.go==0) & (self.dbg_done==1)):
                    m.d.sync += [
                        # Read from SWDIO for SWD, TDO for JTAG
                        self.seqIn.bit_select(self.bitCount,1).eq(Mux(self.isJTAG,self.dbgif.pinsout.bit_select(3,1),self.dbgif.pinsout.bit_select(1,1))),
                        self.bitCount.eq(self.bitCount+1),
                        self.seq_txb.eq(6)
                        ]

            # ------------- ...if this capture is complete then send it back, then decide
            # ------------     if there is still work to be done
            with m.Case(6):
                with m.If((self.seqckCycles==0) | (self.bitCount==0)):
                    # Either this word is full or this sequence is finished
                    with m.If(self.streamIn.ready):
                        m.d.sync += self.bitCount.eq(0)
                        with m.If(self.seqckCycles!=0):
                            # This sequence isn't finished yet
                            m.d.sync += [
                                self.seqIn.eq(0),
                                self.seq_txb.eq(Mux(self.isJTAG,2,Mux(self.seqIsRead,3,2)))
                            ]
                        with m.Else():
                            # This sequence is finished, get the next one if there are any left to get
                            m.d.sync += self.seq_txb.eq(Mux(self.seqCount!=0,1,7))

                        with m.If(self.seqIsRead):
                            m.d.sync += [
                                self.streamIn.payload.eq(self.seqPendingTX),
                                self.streamIn.valid.eq(1),
                                self.seqPendingTX.eq(self.seqIn),
                                self.txedLen.eq(self.txedLen+1),
                            ]
                with m.Else():
                    # This isn't the last bit of this sequence, read or write the next
                    m.d.sync += self.seq_txb.eq(3)

            # ------------- Send the final byte, with last set
            with m.Case(7):
                with m.If(self.streamIn.ready):
                    m.d.sync += [
                        self.streamIn.payload.eq(self.seqPendingTX),
                        self.streamIn.last.eq(self.isV2),
                        self.streamIn.valid.eq(1),
                        self.seq_txb.eq(8)
                    ]

            # ------------- Now decide how to terminate
            with m.Case(8):
                    with m.If(self.isV2 | (self.txedLen==DAP_V1_MAX_PACKET_SIZE)):
                        m.next = 'IDLE'
                    with m.Else():
                        m.next = 'V1PACKETFILL'

    # ----------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------

    def elaborate(self,platform):
        done_cdc      = Signal(2)
        self.dbg_done = Signal()

        m = Module()
        # Reset everything before we start

        m.d.sync += self.streamIn.valid.eq(0)
        m.d.comb += self.streamOut.ready.eq(~self.busy)

        m.submodules.tfrram = self.tfrram = WideRam()

        m.d.comb += self.dbgif.is_jtag.eq(self.isJTAG)

        # Organise the CDC from the debug interface
        m.d.sync += done_cdc.eq(Cat(done_cdc[1],self.dbgif.done))
        m.d.comb += self.dbg_done.eq(done_cdc==0b11)

        # Latch the read data at the rising edge of done signal
        m.d.comb += self.tfrram.we.eq(done_cdc==0b10)

        # By default we are busy unless overridden
        m.d.sync += self.busy.eq(1)

        with m.FSM(domain="sync") as decoder:

    #########################################################################################

            # Collect packet type identifier
            # ------------------------------
            with m.State('IDLE'):
                m.d.sync += [
                    self.txedLen.eq(0),

                    # Default return is packet name followed by 0 (no error)
                    self.txBlock.word_select(0,16).eq(Cat(self.streamOut.payload,C(0,8))),
                    self.txLen.eq(2),

                    # Grab incoming from usb
                    self.rxedLen.eq(1),
                    self.rxBlock.word_select(0,8).eq(self.streamOut.payload),
                ]

                # Only process if this is the start of a packet (i.e. it's not overrrun or similar)
                with m.If(self.streamOut.valid & self.streamOut.ready & self.streamOut.first):
                    m.next = 'PacketSwitch'
                with m.Else():
                    m.d.sync += self.busy.eq(0)

    #########################################################################################

            # Have a packet type, decide how to handle it
            # -------------------------------------------
            with m.State('PacketSwitch'):

                with m.Switch(self.rxBlock.word_select(0,8)):
                    with m.Case(DAP_Disconnect, DAP_ResetTarget, DAP_SWO_Status, DAP_TransferAbort):
                        m.d.sync+= self.rxLen.eq(1)
                        m.next='Dispatch'

                    with m.Case(DAP_Info, DAP_Connect, DAP_SWD_Configure, DAP_SWO_Transport, DAP_SWJ_Sequence,
                                DAP_SWO_Mode, DAP_SWO_Control, DAP_SWO_ExtendedStatus, DAP_JTAG_IDCODE,
                                DAP_JTAG_Sequence,DAP_SWD_Sequence, DAP_JTAG_Configure):
                        m.d.sync+=self.rxLen.eq(2)
                        m.next = 'RxParams'

                    with m.Case(DAP_HostStatus, DAP_SWO_Data, DAP_Delay, DAP_Transfer):
                        m.d.sync+=self.rxLen.eq(3)
                        m.next = 'RxParams'

                    with m.Case(DAP_SWO_Baudrate, DAP_SWJ_Clock, DAP_TransferBlock):
                        m.d.sync+=self.rxLen.eq(5)
                        m.next = 'RxParams'

                    with m.Case(DAP_WriteABORT, DAP_TransferConfigure):
                        m.d.sync+=self.rxLen.eq(6)
                        m.next = 'RxParams'

                    with m.Case(DAP_SWJ_Pins):
                        m.d.sync+=self.rxLen.eq(7)
                        m.next = 'RxParams'

                    with m.Case(DAP_ExecuteCommands,DAP_QueueCommands):
                        m.next = 'Error'

                    with m.Default():
                        m.next = 'Error'

    #########################################################################################

            # Need to collect parameters to go with the command
            # -------------------------------------------------
            with m.State('RxParams'):
                # Grab next byte in this packet
                with m.If(self.streamOut.valid & self.streamOut.ready):
                    m.d.sync += [
                        self.rxBlock.word_select(self.rxedLen,8).eq(self.streamOut.payload),
                        self.rxedLen.eq(self.rxedLen+1)
                    ]

                    # Don't grab more data if we've got what we were commanded for
                    with m.If(self.rxedLen+1==self.rxLen):
                        m.next = 'Dispatch'

                with m.Else():
                    # If we're showing ~valid then this packet is foreshortened
                    with m.If(~self.streamOut.valid):
                        m.next = 'Error'
                    with m.Else():
                        # Otherwise request data
                        m.d.sync += self.busy.eq(0)

    #########################################################################################

            # Dispatch the command - we've got everything for this packet so let's process it
            # -------------------------------------------------------------------------------
            with m.State('Dispatch'):
                with m.Switch(self.rxBlock.word_select(0,8)):

                    # General Commands
                    # ================
                    with m.Case(DAP_Info):
                        self.RESP_Info(m)

                    with m.Case(DAP_HostStatus):
                        self.RESP_HostStatus(m)

                    with m.Case(DAP_Connect):
                        self.RESP_Connect_Setup(m)

                    with m.Case(DAP_Disconnect):
                        self.RESP_Disconnect(m)

                    with m.Case(DAP_WriteABORT):
                        self.RESP_WriteABORT(m)

                    with m.Case(DAP_Delay):
                        self.RESP_Delay(m)

                    with m.Case(DAP_ResetTarget):
                        self.RESP_ResetTarget(m)

                    # Common SWD/JTAG Commands
                    # ========================
                    with m.Case(DAP_SWJ_Pins):
                        self.RESP_SWJ_Pins_Setup(m)

                    with m.Case(DAP_SWJ_Clock):
                        self.RESP_SWJ_Clock(m)

                    with m.Case(DAP_SWJ_Sequence):
                        self.RESP_SWJ_Sequence_Setup(m)

                    # SWD Commands
                    # ============
                    with m.Case(DAP_SWD_Configure):
                        self.RESP_SWD_Configure(m)

                    with m.Case(DAP_SWD_Sequence):
                        self.RESP_Sequence_Setup(m)

                    # SWO Commands
                    # ============
                    # All SWO commands are ignored to create an INVALID response

                    # JTAG Commands
                    # =============
                    with m.Case(DAP_JTAG_Sequence):
                        self.RESP_Sequence_Setup(m)

                    with m.Case(DAP_JTAG_Configure):
                        self.RESP_JTAG_Configure_Setup(m)

                    with m.Case(DAP_JTAG_IDCODE):
                        self.RESP_JTAG_IDCODE_Setup(m)

                    # Transfer Commands
                    # =================
                    with m.Case(DAP_TransferConfigure):
                        self.RESP_TransferConfigure(m)

                    with m.Case(DAP_Transfer):
                        self.RESP_Transfer_Setup(m)

                    with m.Case(DAP_TransferBlock):
                        self.RESP_TransferBlock_Setup(m)

                    # AOB
                    # ===
                    with m.Default():
                        m.next = 'Error'

    #########################################################################################

            # Cases for error conditions
            # --------------------------
            with m.State('Error'):
                self.RESP_Invalid(m)

    #########################################################################################

            # Cases for individual process handlers
            # -------------------------------------
            with m.State('DAP_SWJ_Pins_PROCESS'):
              self.RESP_SWJ_Pins_Process(m)

            with m.State('DAP_SWO_Data_PROCESS'):
              self.RESP_Not_Implemented(m)

            with m.State('DAP_SWJ_Sequence_PROCESS'):
                self.RESP_SWJ_Sequence_Process(m)

            with m.State('DAP_JTAG_Sequence_PROCESS'):
              self.RESP_Sequence_PROCESS(m)

            with m.State('DAP_Transfer_PROCESS'):
              self.RESP_Transfer_Process(m)

            with m.State('DAP_TransferBlock_PROCESS'):
              self.RESP_TransferBlock_Process(m)

            with m.State('DAP_Sequence_PROCESS'):
              self.RESP_Sequence_PROCESS(m)

            with m.State('UPLOAD_RXED_DATA'):
              self.RESP_Transfer_Complete(m)

            with m.State('JTAG_IDCODE_Process'):
              self.RESP_JTAG_IDCODE_Process(m)

            with m.State('JTAG_Configure_PROCESS'):
              self.RESP_JTAG_Configure_Process(m)

            with m.State('DAP_Wait_Done'):
                self.RESP_Wait_Done(m)

            with m.State('DAP_Wait_Connect_Done'):
                self.RESP_Wait_Connect_Done(m)

    #########################################################################################

            with m.State('RESPOND'):
                m.d.sync += [
                    self.streamIn.valid.eq(self.txedLen<self.txLen),
                    self.streamIn.payload.eq(self.txBlock.word_select(self.txedLen,8)),

                    # This is the end of the packet if we've filled the length and it's v2
                    self.streamIn.last.eq(self.isV2 & (self.txedLen==self.txLen-1))
                    ]

                with m.If(self.streamIn.ready & self.streamIn.valid):
                    m.d.sync += [
                        self.txedLen.eq(self.txedLen+1),
                        self.streamIn.valid.eq(0)
                    ]

                with m.If(self.txedLen==self.txLen):
                    with m.If(self.isV2 | (self.txedLen==DAP_V1_MAX_PACKET_SIZE)):
                        # Everything is transmitted, return to idle condition
                        m.next = 'IDLE'
                    with m.Else():
                        m.next = 'V1PACKETFILL'

            with m.State('V1PACKETFILL'):
                m.d.sync += [
                    self.streamIn.valid.eq(self.txedLen<DAP_V1_MAX_PACKET_SIZE),
                    self.streamIn.payload.eq(0),
                ]

                with m.If(self.streamIn.ready & self.streamIn.valid):
                    m.d.sync+=[
                        self.txedLen.eq(self.txedLen+1),
                        self.streamIn.valid.eq(0)
                        ]

                with m.If(self.txedLen==DAP_V1_MAX_PACKET_SIZE):
                    m.next = 'IDLE'


    #########################################################################################

        return m
