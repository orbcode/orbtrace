`default_nettype none
//
// SPDX-License-Identifier: BSD-3-Clause
//
// jtagIF
// ======
//
// Working from ARM Debug Interface Architecture Specification ADIv5.0 to ADIv5.2
// Modelled on structure from DAPLink implementation at
// // https://github.com/ARMmbed/DAPLink which in Apache 2.0 Licence.
// This gateware uses (obviously!) uses no code from DAPLink and is under BSD licence.
//

parameter JTAG_CMD_IR     = 0;    // Set IR
parameter JTAG_CMD_TFR    = 1;    // Perform transfer
parameter JTAG_CMD_ABORT  = 2;    // Abort transfer
parameter JTAG_CMD_READID = 3;    // Read ID Code

module jtagIF (
		input             rst,      // Reset synchronised to clock
                input             clk,

	// Downwards interface to the JTAG pins
                input             tdo,      // Test Data Out from targets
                output reg        tdi,      // Test Data In to targets
                output reg        tms,      // Test Mode Select to targets
                output            tck,      // Test clock out to targets

                input [2:0]       dev,      // Device in chain we're talking to
                input [2:0]       ndev,     // Number of devices in JTAG chain-1
                input [24:0]      irlenx,   // Length of each IR-1, 5x5 bits

                input             rising,   // Flag indicating rising edge to target
                input             tclk_in,  // Input target clock

	// Upwards interface to command controller

                input [1:0]       cmd,      // Command for JTAG IF to carry out
                input [1:0]       addr32,   // Address bits 3:2 for message
                input             rnw,      // Set for read, clear for write
                input             apndp,    // AP(1) or DP(0) access?
                input [31:0]      dwrite,   // Most recent data from us
                output reg [2:0]  ack,      // Most recent ack status
                output reg [31:0] dread,    // Data read from target

                output            canary,   // Debug, in case it's needed
                input             go,       // Trigger
                output            idle      // Response
		);

   // Internals =========================================================================
   reg [2:0]                      jtag_state;                 // current state of machine
   reg [2:0]                      next_state;     // State to switch to after current one
   reg [4:0]                      tmsbits;                  // Number of TMS bits to send
   reg [4:0]                      tdxbits;             // Number of data bits to exchange

   reg [2:0]                      tmscount;            // Counter for tms bits being sent
   reg [5:0]                      tdxcount;    // Counter for data bits being transferred

   reg [2:0]                      devcount;     // Counter for number of devices in chain


   parameter ST_JTAG_IDLE        = 0;
   parameter ST_JTAG_TMSOUT      = 1;
   parameter ST_JTAG_READID      = 2;
   parameter ST_JTAG_READID_DONE = 3;
   parameter ST_JTAG_DATA        = 4;
   parameter ST_JTAG_LOADIR      = 5;
   parameter ST_JTAG_IR          = 6;

   assign idle      = (jtag_state==ST_JTAG_IDLE);
   assign tck       = (idle)?tclk_in:1;

   assign canary    = 0;
   always @(posedge clk)
     begin
        if (rising)
          begin
             case (jtag_state)
               ST_JTAG_IDLE: // Idle waiting for something to happen ====================
                 begin
                    if (go)                             // Request to start a transfer
                      begin
                         case (cmd)
                           JTAG_CMD_READID:  // Read device id -----------------
                             begin
                                tmsbits <= { 3'b001 };
                                tmscount <= 3;
                                next_state <= ST_JTAG_READID;
                                jtag_state <= ST_JTAG_TMSOUT;
                             end

                           JTAG_CMD_ABORT: // Abort, reset all TAPs ------------
                             begin
                                tmsbits <= { 5'b11111 };
                                tmscount <= 5;
                                next_state <= ST_JTAG_IDLE;
                                jtag_state <= ST_JTAG_TMSOUT;
                             end

                           JTAG_CMD_IR: // Set IR ------------------------------
                             begin
                                tmsbits <= { 4'b0011 };
                                tmscount <= 4;
                                next_state <= ST_JTAG_LOADIR;
                                jtag_state <= ST_JTAG_TMSOUT;
                             end

                         endcase // case (cmd)
                      end
                 end // case: ST_JTAG_IDLE

               ST_JTAG_LOADIR: // Load IR ===============================================
                 begin
                    devcount <= 0;
                    tdxcount <= 0;
                 end

               ST_JTAG_READID: // Get to shift-DR state and bypass before data ==========
                 begin
                    devcount <= 0;
                    tdxcount <= 0;
                    tdxbits  <= 32-1;
                    next_state <= ST_JTAG_READID_DONE;
                    jtag_state <= ST_JTAG_DATA;
                 end

               ST_JTAG_READID_DONE: // Finished ID read, so return idle =================
                 begin
                    next_state <= ST_JTAG_IDLE;
                    tmsbits <= 3'b011;
                    jtag_state <= ST_JTAG_TMSOUT;
                 end

               ST_JTAG_IR: // Clock IR in ===============================================
                 begin
                    tdi <= 1;
                 end

               ST_JTAG_DATA:   // Clock data in/out =====================================
                 begin
                    tdi <= 0;
                    tdxcount <= tdxcount + 1;

                    if (devcount==dev)
                      begin
                         if (rnw)
                           dread <= { tdo,dread[31:1] };
                         else
                           tdi <= dwrite[tdxcount];
                      end

                    if (tdxbits==tdxcount)
                      begin
                         if (devcount==ndev)
                           jtag_state <= next_state;
                         else
                           begin
                              devcount <= devcount + 1;
                              tdxbits <= 32-1;
                              tdxcount <= 0;
                           end
                      end
                 end // case: ST_JTAG_DATA


               ST_JTAG_TMSOUT: // clock out defined tms bits ============================
                 begin
                    tms     <= tmsbits[0];
                    tmsbits <= { 1'b0,tmsbits[4:1] };
                    tmscount <= tmscount-1;
                    if (tmscount==1)
                      jtag_state <= next_state;
                 end


             endcase // case (jtag_state)
          end // if (rising)
     end // always @ (posedge clk)
endmodule // jtagIF
