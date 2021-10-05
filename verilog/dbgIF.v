`default_nettype none

// dbgIF
// =====
//
// Working from ARM Debug Interface Architecture Specification ADIv5.0 to ADIv5.2
//
// Debug interface covering JTAG, SWJ and SWD use cases.
// Also deals with power pins.
//
// This gateware is under BSD licence.
//
// Commands are loaded by putting the command id into command, setting any registers and then
// taking 'go' true. 'done' will go false when the command has started, then go should be
// returned false. 'done' will go true when the command completes. err will be set for errors.
// For streams (specifically CMD_TRANSACT only) 'go' can be taken true again to prime the next
// transfer.
//
//  CMD_RESET       : Reset target, return after timeout or when target is out of reset.
//                    Wait for number of uS set via CMD_SET_RST_TMR, or 10mS if no explicit
//                    time has been set.  Then wait until reset pin returns high, or a guard
//                    period the same as the reset period expires.
//
//  CMD_PINS_WRITE  : Go to SWJ mode and write pins specified in pinsin[7:0], masked
//                    by pinsin[15:8], wait and then return pins in pinsout[7:0].
//                    dwrite is the time in uS to wait. If dwrite is zero then the period to
//                    wait is one target interface clock half-cycle.
//                          Bit Writable    Name              Notes
//                           0      Y     SWCLK/TCK
//                           1      Y     SWDIO/TMS
//                           2      Y     TDI
//                           3            TDO
//                           4      Y     SWWR          1==Output SPEC EXTENSION
//                           5            1'b1
//                           6            nRESET_STATE     SPEC EXTENSION
//                           7      Y     nRESET
//
//  CMD_TRANSACT    : Execute command transaction on target interface.
//                          addr32  Bits 2 & 3 of address
//                          rnw     Read(1) not Write(0)
//                          apndp   ap(1) not dp(0)
//                          ack     returned ack from command
//                          dwrite  any data to write
//                          dread   any data returned
//
//  CMD_SET_SWD     : Set interface to SWD mode.
//
//  CMD_SET_JTAG    : Set interface to JTAG mode.
//
//  CMD_SET_SWJ     : Set interface to SWJ mode.
//
//  CMD_SET_CLKDIV  : Set clock divisor for target interface (in dwrite).
//
//  CMD_SET_SWD_CFG : Set turnaround clock ticks and dataPhase for SWD mode
//                          dwrite[1:0]  turnaround-1 (1..4 cycles)
//                          drwrite[2]   dataphase (cooloff of 32 additional bits on WAIT/FAULT)
//
//  CMD_SET_JTAG_CFG: Set IR length and number of devices in chain
//                          dwrite[4:0]  number of devices in chain (0..5)
//                          dwrite[9:5]   ir length for first device (0..31)+1
//                          dwrite[14:10] ir length for second device (0..31)+1
//                          dwrite[19:15] ir length for third device (0..31)+1
//                          dwrite[24:20] ir length for fourth device (0..31)+1
//                          dwrite[29:25] ir length for fifth device (0..31)+1
//
//  CMD_JTAG_RESET  : Reset JTAG TAPs
//
//  CMD_WAIT        : Wait for prescribed number of uS in dwrite
//
//  CMD_CLR_ERR     : Clear error status
//
//  CMD_SET_RST_TMR : Set reset and reset guard time in uS
//
//  CMD_SET_TFR_CFG : Return pin configuration to selected option (used after taking over the
//                    interface pins with CMD_SET_SWJ etc.)
//

module dbgIF #(parameter CLK_FREQ=120000000, parameter DEFAULT_SWCLK=1000000, parameter DEFAULT_RST_TIMEOUT_USEC=300) (
		input             rst,
                input             clk,

        // Gross control, power etc.
                input             vsen,            // When 1, provide power to VS (pins 11 & 13 on 20 pin header)
                input             vdrive,          // When 1, provide power to Vdrive (pin 1 on 10 & 20 pin header)

	// Downwards interface to the pins
                input             swdi,            // DIO pin from target
                output            tms_swdo,        // TMS or DIO pin to target when in SWD mode
                output            swwr,            // Direction of DIO pin when in SWD mode
                output            tck_swclk,       // Clock pin to target
                output            tdi,             // TDI pin to target
                input             tdo_swo,         // TDO/SWO pin from target

                input             tgt_reset_state, // Current state of tgt_reset
                output            tgt_reset_pin,   // Output pin to pull target reset low
                output            nvsen_pin,       // Output pin to control vsen
                output            nvdrive_pin,     // Output pin to control vdrive

	// Interface to command controller
                input [1:0]       addr32,          // Address bits 3:2 for message
                input             rnw,             // Set for read, clear for write
                input             apndp,           // AP(1) or DP(0) access?
                output [2:0]      ack,             // Most recent ack status

                input  [31:0]     dwrite,          // Most recent data or parameter to write
                output [31:0]     dread,           // Data read from target
                input  [15:0]     pinsin,          // Pin setting information to target (upper 8 bits mask)
                output [7:0]      pinsout,         // Pin information from target

        // Event triggers and responses
                input [3:0]       command,         // Command to be performed
                input             go,              // Trigger
                output            done,            // Response
                output reg        perr,            // Indicator of a error in the transfer

        // JTAG specifics
                input [2:0]       dev,             // Device on the chain to be communicated with

        // Canary for debug
                output            canary,

        // Posted read management
                output reg        postedMode,      // Flag indicating we're in posted mode
                output reg        ignoreData,      // Ignore the data returned from this call (for the case of the start of posted read)
                output reg        again            // Take the data returned from this call as last AP read, then repeat the request
	      );

   parameter TICKS_PER_USEC=CLK_FREQ/1000000;
   parameter DEFAULT_IF_TICKS_PER_CLK=((CLK_FREQ+(DEFAULT_SWCLK>>1))/(DEFAULT_SWCLK<<1))-1;

   // Control commands
   parameter CMD_RESET       = 0;
   parameter CMD_PINS_WRITE  = 1;
   parameter CMD_TRANSACT    = 2;
   parameter CMD_SET_SWD     = 3;
   parameter CMD_SET_JTAG    = 4;
   parameter CMD_SET_SWJ     = 5;
   parameter CMD_SET_JTAG_CFG= 6;
   parameter CMD_SET_CLK     = 7;
   parameter CMD_SET_SWD_CFG = 8;
   parameter CMD_WAIT        = 9;
   parameter CMD_CLR_ERR     = 10;
   parameter CMD_SET_RST_TMR = 11;
   parameter CMD_SET_TFR_CFG = 12;
   parameter CMD_JTAG_GET_ID = 13;
   parameter CMD_JTAG_RESET  = 14;

   // Commands down to JTAG layer
   parameter JTAG_CMD_IR     = 0;    // Set IR
   parameter JTAG_CMD_TFR    = 1;    // Perform transfer
   parameter JTAG_CMD_ABORT  = 2;    // Abort transfer
   parameter JTAG_CMD_READID = 3;    // Read ID Code

   // Comms modes - order is important to ensure interface starts in SWD mode by default
   parameter MODE_SWD     = 0;
   parameter MODE_SWJ     = 1;
   parameter MODE_JTAG    = 2;
   parameter MODE_LOCAL   = 3;

   // Slowest clock we will accept (This is ~390K for a 100MHz input clock)
   parameter CDIV_LOG2    = 8;
   parameter MIN_CLOCK    = CLK_FREQ/(2**CDIV_LOG2);
   parameter MAX_CLOCK    = (CLK_FREQ/2);

   // Internals =======================================================================
   reg [(CDIV_LOG2-1):0]          cdivcount;       // divisor for external clock
   reg [10:0]                     usecsdiv;        // Divider for usec
   reg [31:0]                     modeshift;       // Shift register for changing mode
   reg [31:0]                     divreg;          // Division register
   reg [22:0]                     usecsdown;       // usec downcounter
   reg [1:0]                      cdc_go;          // Clock domain crossed go

   reg [(CDIV_LOG2-1):0]          clkDiv;          // Divisor per clock change to target

   // SWD Related
   reg [1:0]                      turnaround;      // Number of cycles for turnaround when in SWD mode
   reg                            dataphase;       // Indicator of if a dataphase is needed on WAIT/FAULT
   reg [7:0]                      idleCycles;      // Number of cycles before return to idle

   // JTAG Related
   reg [2:0]                      ndev;            // Number of devices in JTAG chain
   reg [24:0]                     irlenx;          // Length of each IR-1, 5x5 bits

   // DBG (adiv protocol level) related
   reg [22:0]                     rst_timeout;     // Default time for a reset
   reg [1:0]                      commanded_mode;  // Mode that the interface is requested to be in
   reg [1:0]                      active_mode;     // Mode that its currently switched to
   reg [3:0]                      dbg_state;       // Current state of debug handler
   reg [8:0]                      state_step;      // Stepping through comms states
   reg                            readRDBUFF;      // Flag to read RDBUFF rather than commanded register
   reg                            old_tgtclk;      // Historic swclock to see when an edge occured

   parameter ST_DBG_IDLE                 = 0;
   parameter ST_DBG_RESETTING            = 1;
   parameter ST_DBG_RESET_GUARD          = 2;
   parameter ST_DBG_PINWRITE_WAIT        = 3;
   parameter ST_DBG_WAIT_INFERIOR_START  = 4;
   parameter ST_DBG_WAIT_INFERIOR_FINISH = 5;
   parameter ST_DBG_WAIT_GOCLEAR         = 6;
   parameter ST_DBG_WAIT_TIMEOUT         = 7;
   parameter ST_DBG_WAIT_CLKCHANGE       = 8;
   parameter ST_DBG_ESTABLISH_MODE       = 9;
   parameter ST_DBG_CALC_DIV             = 10;

   // Pins driven by swd (MODE_SWD)
   wire                           swd_swdo;
   wire                           swd_swclk;
   wire                           swd_swwr;
   wire [2:0]                     swd_ack;
   wire [31:0]                    swd_dread;
   wire                           swd_perr;
   wire                           swd_idle;

   // Pins driven by jtag (MODE_JTAG)
   wire                           jtag_tdo;
   wire                           jtag_tdi;
   wire                           jtag_tck;
   wire                           jtag_tms;
   wire                           jtag_wr;
   wire [2:0]                     jtag_ack;
   wire [31:0]                    jtag_dread;
   wire                           jtag_idle;
   reg [1:0]                      jtag_cmd;
   reg [2:0]                      jtag_dev;

   // Pins driven by pin_write (MODE_SWJ)
   wire                           pinw_nreset = pinsin[8+7]?pinsin[7]:1;
   wire                           pinw_tdi    = pinsin[8+2]?pinsin[2]:1;
   wire                           pinw_swwr   = pinsin[8+4]?pinsin[4]:0;
   wire                           pinw_swdo   = pinsin[8+1]?pinsin[1]:0;

   reg                            pinw_swclk;
   reg                            root_tgtclk;

   // Pins driven by local
   reg                           local_tgtclk;
   reg                           local_swdo;

   // Mux submodule outputs to this module outputs
   assign canary        = tdo_swo;
   assign nvsen_pin     = ~vsen;
   assign nvdrive_pin   = ~vdrive;
   assign tms_swdo      = ((dbg_state==ST_DBG_IDLE) || (active_mode==MODE_SWJ))?pinw_swdo:
                          (active_mode==MODE_SWD)?swd_swdo:
                          (active_mode==MODE_JTAG)?jtag_tms:
                          1'b0;
   assign jtag_tdo      = tdo_swo;
   assign jtag_wr       = 1'b1;
   assign tdi           = ((dbg_state==ST_DBG_IDLE) || (active_mode==MODE_SWJ))?pinw_tdi:(active_mode==MODE_JTAG)?jtag_tdi:1'b1;
   assign swwr          = ((dbg_state==ST_DBG_IDLE) || (active_mode==MODE_SWJ))?pinw_swwr:(active_mode==MODE_SWD)?swd_swwr:(active_mode==MODE_JTAG)?jtag_wr:1'b0;
   assign ack           = (active_mode==MODE_SWD)?swd_ack:jtag_ack;
   assign dread         = (active_mode==MODE_SWD)?swd_dread:jtag_dread;
   assign tck_swclk     = ((dbg_state==ST_DBG_IDLE) || (active_mode==MODE_SWJ))?pinw_swclk:(active_mode==MODE_SWD)?swd_swclk:(active_mode==MODE_JTAG)?jtag_tck:1'b1;

   assign tgt_reset_pin = ~((active_mode==MODE_SWJ)?pinw_nreset:(dbg_state!=ST_DBG_RESETTING));
   assign pinsout       = { tgt_reset_pin, tgt_reset_state, 1'b1, swwr, tdo_swo, tdi, swdi, tck_swclk };

   // Edge calculations
   wire        done        = (dbg_state==ST_DBG_IDLE);
   wire        anedge      = (old_tgtclk^root_tgtclk);
   wire        fallingedge = (anedge && ((~root_tgtclk) || (dbg_state==ST_DBG_IDLE)));
   wire        risingedge  = (anedge && root_tgtclk);

   // Internals for state management
   wire        if_go       = (dbg_state==ST_DBG_WAIT_INFERIOR_START);

   // Connection to the SWD Interface
   // ===============================
   swdIF swd_instance (
	      .rst(rst),
              .clk(clk),

              .swdi(swdi),
              .swdo(swd_swdo),
              .swclk_in(root_tgtclk),
              .swclk_out(swd_swclk),
              .falling(fallingedge),
              .rising(risingedge),
              .swwr(swd_swwr),
              .turnaround(turnaround),
              .dataphase(dataphase),
              .idleCycles(idleCycles),

              // If this is the end of a AP read sequence it needs to be overridden
              // With a RDBUFF read, no matter what was originally asked for.
              .addr32(readRDBUFF?2'd3:addr32),
              .rnw(readRDBUFF?1'b1:rnw),
              .apndp(readRDBUFF?1'b0:apndp),

              .dwrite(dwrite[31:0]),
              .ack(swd_ack),
              .dread(swd_dread),
              .perr(swd_perr),

              .go(if_go && (active_mode==MODE_SWD)),
              .idle(swd_idle)
	      );

   // Connection to the JTAG Interface
   // ================================
   jtagIF jtag_instance (
	      .rst(rst),
              .clk(clk),

              .tdo(jtag_tdo),
              .tdi(jtag_tdi),
              .tms(jtag_tms),
              .tck(jtag_tck),
              .dev(dev),
              .ndev(ndev),
              .irlenx(irlenx),

              .rising(risingedge),
              .tclk_in(root_tgtclk),

              .cmd(jtag_cmd),

              // If this is the end of a AP read sequence it needs to be overridden
              // With a RDBUFF read, no matter what was originally asked for.
              .addr32(readRDBUFF?2'd3:addr32),
              .rnw(readRDBUFF?1'b1:rnw),
              .apndp(readRDBUFF?1'b0:apndp),

              .dwrite(dwrite[31:0]),
              .ack(swd_ack),
              .dread(jtag_dread),

              .go(if_go && (active_mode==MODE_JTAG)),
              .idle(jtag_idle)
		         );

   //////////////////////////////////////////////////////////////////////////////////////////////////////
   always @(posedge clk, posedge rst)

     begin
	if (rst)
	  begin
             pinw_swclk  <= 1;
             cdivcount   <= 1;
             clkDiv      <= DEFAULT_IF_TICKS_PER_CLK;
             rst_timeout <= DEFAULT_RST_TIMEOUT_USEC;
             dbg_state   <= ST_DBG_IDLE;
	  end
	else
          begin
             // CDC the go signal
             cdc_go <= {cdc_go[0],go};
             old_tgtclk <= root_tgtclk;

             // Run the clock
             cdivcount<=cdivcount?cdivcount-1:clkDiv;
             if (!cdivcount)
               root_tgtclk <= ~root_tgtclk;

             // The usecs counter can run all of the time, it's independent
             usecsdiv<=usecsdiv?usecsdiv-1:TICKS_PER_USEC-1;


             case(dbg_state)
               ST_DBG_IDLE: // Command request ========================================================
                 if (cdc_go==2'b11)
                   begin
                      // Reset any outstanding error indication
                      perr       <= 0;
                      case(command)
                        CMD_PINS_WRITE: // Write pins specified in call -------------------------------
                          if (fallingedge)
                          begin
                             active_mode <= MODE_SWJ;

                             // All bets are off on posting, don't even try
                             postedMode  <= 0;
                             pinw_swclk <= pinsin[8+0] ?pinsin[0]:0;

                             if (dwrite)
                               begin
                                  usecsdown   <= dwrite[31:0];
                                  dbg_state <= ST_DBG_WAIT_TIMEOUT;
                               end
                             else
                               begin
                                  // One extra tick to allow the clock edge to propagate
                                  cdivcount  <= clkDiv?clkDiv:1;
                                  dbg_state  <= ST_DBG_WAIT_CLKCHANGE;
                               end
                          end // case: CMD_PINS_WRITE

                        CMD_RESET: // Reset target ----------------------------------------------------
                          if (fallingedge)
                            begin
                               postedMode <= 0;
                               usecsdown <= rst_timeout;
                               usecsdiv  <= TICKS_PER_USEC-1;
                               dbg_state <= ST_DBG_RESETTING;
                            end

                        CMD_TRANSACT: // Execute transaction on target interface ----------------------
                          if (fallingedge)
                            begin
                               active_mode <= commanded_mode;
                               // These signals are only active for the duration of a single transaction
                               // but if the previous return was a WAIT then they remain valid because
                               // we are effectively still processing the transaction..we will repeat it
                               if (swd_ack!=3'b010)
                                 begin
                                    ignoreData <= 0;
                                    again      <= 0;
                                    readRDBUFF <= 0;
                                 end

                               if (postedMode && ~(rnw && apndp))
                                 begin
                                    // We are leaving posted mode, read the last octet and indicate
                                    // this one should be sent again
                                    postedMode <= 1'b0;
                                    again      <= (addr32!=3);
                                    readRDBUFF <= 1'b1;
                                 end
                               else
                                 if (rnw && apndp && (~postedMode))
                                 begin
                                    // We are entering posted mode warn upstairs to ignore this data
                                    postedMode <= 1'b1;
                                    ignoreData <= 1'b1;
                                 end

                               dbg_state   <= ST_DBG_WAIT_INFERIOR_START;
                            end

                        CMD_SET_SWD: // Set SWD mode --------------------------------------------------
                          if (fallingedge)
                          begin
                             commanded_mode <= MODE_SWD;
                             state_step     <= 0;
                             modeshift      <= 32'h0000e79e;
                             postedMode     <= 0;
                             dbg_state      <= ST_DBG_ESTABLISH_MODE;
                          end

                        CMD_SET_JTAG: // Set JTAG mode ------------------------------------------------
                          if (fallingedge)
                          begin
                             commanded_mode <= MODE_LOCAL;
                             state_step     <= 0;
                             modeshift      <= 32'h0000E73C;
                             postedMode     <= 0;
                             dbg_state      <= ST_DBG_ESTABLISH_MODE;
                          end

                        CMD_JTAG_GET_ID: // Get ID of specified JTAG device ---------------------------
                          begin
                             commanded_mode <= MODE_JTAG;
                             jtag_cmd       <= JTAG_CMD_READID;
                             jtag_dev       <= dwrite[2:0];
                             dbg_state      <= ST_DBG_WAIT_INFERIOR_START;
                          end

                        CMD_JTAG_RESET: // Reset all JTAG TAPs ----------------------------------------
                          begin
                             commanded_mode <= MODE_JTAG;
                             jtag_cmd       <= JTAG_CMD_ABORT;
                             dbg_state      <= ST_DBG_WAIT_INFERIOR_START;
                          end

                        CMD_SET_SWJ: // Set SWJ mode --------------------------------------------------
                          begin
                             commanded_mode <= MODE_LOCAL;
                             pinw_swclk     <= 1;
                             dbg_state      <= ST_DBG_WAIT_GOCLEAR;
                          end

                        CMD_SET_CLK: // Set clock -----------------------------------------------------
                          begin
                             if ((dwrite<MIN_CLOCK) || (dwrite>MAX_CLOCK))
                               begin
                                  perr       <= 1'b1;
                                  dbg_state  <= ST_DBG_WAIT_GOCLEAR;
                               end
                             else
                               begin
                                  clkDiv     <= 0;
                                  divreg     <= MAX_CLOCK;
                                  dbg_state  <= ST_DBG_CALC_DIV;
                               end
                          end

                        CMD_SET_SWD_CFG: // Set SWD Config ---------------------------------------------
                          begin
                             turnaround   <= dwrite[1:0];
                             dataphase    <= dwrite[2];
                             dbg_state    <= ST_DBG_WAIT_GOCLEAR;
                          end

                        CMD_SET_JTAG_CFG: // Set JTAG Config ------------------------------------------
                          begin
                             ndev         <= dwrite[3:0];
                             irlenx       <= dwrite[29:5];
                             dbg_state    <= ST_DBG_WAIT_GOCLEAR;
                          end

                        CMD_SET_TFR_CFG: // Set idle cycles -------------------------------------------
                          begin
                             idleCycles   <= dwrite[7:0];
                             dbg_state    <= ST_DBG_WAIT_GOCLEAR;
                          end

                        CMD_WAIT: // Wait for specified number of uS ----------------------------------
                          begin
                             usecsdown    <= dwrite;
                             usecsdiv     <= TICKS_PER_USEC-1;
                             dbg_state <= ST_DBG_WAIT_TIMEOUT;
                          end

                        CMD_CLR_ERR: // Clear error status --------------------------------------------
                          dbg_state <= ST_DBG_WAIT_GOCLEAR;

                        CMD_SET_RST_TMR: // Set reset timer -------------------------------------------
                          begin
                             rst_timeout <= dwrite;
                             dbg_state   <= ST_DBG_WAIT_GOCLEAR;
                          end

                        default: // Unknown, set an error ---------------------------------------------
                          begin
                             perr         <= 1;
                             dbg_state    <= ST_DBG_WAIT_GOCLEAR;
                          end
                      endcase // case (command)
                      end // if (go)

               ST_DBG_WAIT_GOCLEAR: // Waiting for go indication to clear =================================
                 if (cdc_go!=2'b11)
                   dbg_state <= ST_DBG_IDLE;

               ST_DBG_CALC_DIV: // Calculate division for debug clock =====================================
                 if (divreg>dwrite)
                   begin
                      divreg     <= divreg-dwrite;
                      clkDiv     <= clkDiv+1;
                   end
                 else
                   begin
                      cdivcount <= clkDiv;
                      dbg_state <= ST_DBG_WAIT_GOCLEAR;
                   end

               ST_DBG_WAIT_INFERIOR_FINISH: // Waiting for inferior to complete its task ===================
                 begin
                    case (active_mode)
                      MODE_SWD:
                        if (swd_idle)
                          begin
                             dbg_state <= ST_DBG_WAIT_GOCLEAR;
                             perr      <= swd_perr;
                             if (swd_perr | ((ack != 3'b001) & (ack !=3'b010)))
                               begin
                                  postedMode <= 0;
                                  ignoreData <= 0;
                                  again      <= 0;
                                  readRDBUFF <= 0;
                               end
                          end // if (swd_idle)

                      MODE_JTAG:
                        if (jtag_idle)
                          begin
                             dbg_state <= ST_DBG_WAIT_GOCLEAR;
                          end

                      default:
                        begin
                           perr      <= 1'b1;
                           dbg_state <= ST_DBG_WAIT_GOCLEAR;
                        end
                    endcase // case (active_mode)
                 end

               ST_DBG_WAIT_INFERIOR_START: // Waiting for inferior to start its task =======================
                 begin
                    case (active_mode)
                      MODE_SWD:
                        if (~swd_idle)
                          dbg_state <= ST_DBG_WAIT_INFERIOR_FINISH;

                      MODE_JTAG:
                        if (~jtag_idle)
                          dbg_state <= ST_DBG_WAIT_INFERIOR_FINISH;

                      default:
                        begin
                           perr      <= 1'b1;
                           dbg_state <= ST_DBG_WAIT_GOCLEAR;
                        end
                    endcase // case (active_mode)
                 end

               ST_DBG_WAIT_TIMEOUT: // Waiting for timeout to complete ====================================
                 if (!usecsdown)
                   dbg_state <= ST_DBG_WAIT_GOCLEAR;

               ST_DBG_WAIT_CLKCHANGE: // Waiting for clock state to change ================================
                 if (fallingedge)
                   dbg_state <= ST_DBG_WAIT_GOCLEAR;

               ST_DBG_RESETTING: // We are in reset =======================================================
                 if (!usecsdown)
                   begin
                      usecsdown <= rst_timeout;
                      dbg_state <= ST_DBG_RESET_GUARD;
                   end

               ST_DBG_RESET_GUARD: // We have finished reset, but wait for chip to ack ====================
                 if ((tgt_reset_state) || (!usecsdown))
                   dbg_state<=ST_DBG_WAIT_GOCLEAR;

               ST_DBG_ESTABLISH_MODE: // We want to set a specific mode ===================================
                 begin
                    local_tgtclk<=root_tgtclk;

                    // Stay in sync with clock that is given to inferiors
                    if (fallingedge)
                      begin
                         // Our changes happen on the falling edge (i.e. pinw_swclk currently high)
                         if ((state_step<50) || (state_step>65)) local_swdo<=1'b1;
                         else
                           begin
                              local_swdo<=modeshift[0];
                              modeshift<={1'b0,modeshift[15:1]};
                           end
                         if (state_step>115)
                           local_swdo<=0;
                         state_step<=state_step+1;
                      end // if (falledge)
                    else
                      if (state_step==118)
                        begin
                           local_swdo  <= 0;
                           local_tgtclk <= 1;
                           dbg_state<=ST_DBG_WAIT_GOCLEAR;
                        end
                 end // case: ST_DBG_ESTABLISH_MODE
             endcase // case (dbg_state)
          end // else: !if(rst)
     end // always @ (posedge clk, posedge rst)
endmodule // dbgIF
