`default_nettype none
//
// SPDX-License-Identifier: BSD-3-Clause
//
// swdIF
// =====
//
// Working from ARM Debug Interface Architecture Specification ADIv5.0 to ADIv5.2
// Modelled on structure from DAPLink implementation at
// // https://github.com/ARMmbed/DAPLink which in Apache 2.0 Licence.
// This gateware uses (obviously!) uses no code from DAPLink and is under BSD licence.
//
module swdIF (
		input             rst,      // Reset synchronised to clock
                input             clk,

	// Downwards interface to the SWD pins
                input             swdi,     // DIO pin from target
                output            swdo,     // DIO pin to target
                input             falling,  // Flag indicating falling edge to target
                input             rising,   // Flag indicating rising edge to target
                input             swclk_in, // Input swclock
                output            swclk_out,// swclk out
                output            swwr,     // Direction of DIO pin

        // Configuration
                input [1:0]       turnaround, // Clock ticks per turnaround
                input             dataphase,  // Does a dataphase follow WAIT/FAULT?
                input [7:0]       idleCycles, // How many idlecycles to apply

	// Upwards interface to command controller
                input [1:0]       addr32,   // Address bits 3:2 for message
                input             rnw,      // Set for read, clear for write
                input             apndp,    // AP(1) or DP(0) access?
                input [31:0]      dwrite,   // Most recent data from us
                output reg [2:0]  ack,      // Most recent ack status
                output reg [31:0] dread,    // Data read from target
                output reg        perr,     // Indicator of a parity error
                output            canary,   // Debug, in case it's needed
                input             go,       // Trigger
                output            idle      // Response
		);

   // Internals ======================================================================
   reg [2:0]                      swd_state;               // current state of machine

   reg [7:0]                      spincount;     // Counter for additional turn cycles

   reg [5:0]                      bitcount;      // Counter for bits being transferred
   reg                            par;                             // Parity construct
   reg [31:0]                     rd;       // The read data being prepared for return


   // States of the reception process
   parameter ST_IDLE         = 0;
   parameter ST_HDR_TX       = 1;
   parameter ST_TRN1         = 2;
   parameter ST_ACK          = 3;
   parameter ST_TRN2         = 4;
   parameter ST_DATA         = 5;
   parameter ST_COOLING      = 6;

   // Elements of the transmission frame
   parameter PROT_HEAD_END   = 7;
   parameter PROT_TRN1       = 8;
   parameter PROT_ACK        = 9;
   parameter PROT_ACK_END    = 11;
   parameter PROT_TRN2       = 12;
   parameter PROT_DATA       = 13;
   parameter PROT_PAR        = 46;
   parameter PROT_EOF        = 47;

   // Maintain a frame ready to go...
   //                   46    45..13   12   11..9   8     7     6
   //                 Parity   Data     T   Ack    T    Park  Stop
   wire [46:0] bits = { par,  dwrite, 1'b0, 3'b0, 1'b0, 1'b1, 1'b0,
   //                                   5
   //                                Parity
                        apndp^rnw^addr32[1]^addr32[0],
   //                      4          3        2     1     0
   //                      A3         A2      RnW  APnDP  Start
                        addr32[1], addr32[0], rnw, apndp, 1'b1 };

   // Things sent back to caller...
   assign idle      = (swd_state==ST_IDLE);
   assign swdo      = (idle || (bitcount==PROT_EOF))?0:bits[bitcount];
   assign swclk_out = (idle)?1:swclk_in;
   assign swwr      = (
                       ((swd_state!=ST_IDLE) && (bitcount<PROT_TRN1)) ||     // Header
                       ((~rnw) && (bitcount>PROT_TRN2))       // Writing Data & Parity
                      );
   assign canary    = 0;
   always @(posedge clk)
     begin
        if (rising)
          begin
             rd  <= { swdi, rd[31:1] };     // Keep a sliding frame under construction

             case (swd_state)
               ST_IDLE: // Idle waiting for something to happen ======================
                 begin
                    if (go)                             // Request to start a transfer
                      begin
                         bitcount  <= 0;                  // Index through the tx bits
                         swd_state <= ST_HDR_TX;             // Send the packet header
                         perr      <= 0;                   // Clear any previous error
                         par       <= 0;               // and clear accumulated parity
                      end // if (go)
                 end

               ST_HDR_TX: // Sending the packet header ===============================
                 begin
                    bitcount <= bitcount+1;                  // Next bit of the header
                    if (bitcount==PROT_HEAD_END)                    // Finished header
                      begin
                         spincount  <= turnaround;           // Number of bits of turn
                         swd_state  <= ST_TRN1;              // ...and move to do turn
                      end
                 end

               ST_TRN1: // Performing turnaround =====================================
                 begin
                    spincount<=spincount-1;                        // Turn in progress
                    if (!spincount)                                    // Now finished
                      begin
                         bitcount  <= PROT_ACK;     // Move to the ACK bits (not used)
                         swd_state <= ST_ACK;              // ..and go collect the ACK
                      end
                 end

               ST_ACK: // Collect the ack bits =======================================
                 begin
                    bitcount <= bitcount+1;                // Clicking through the ACK
                    if (bitcount==PROT_ACK_END)                       // Have now done
                      begin
                         ack <= {swdi,rd[31:30]};                     // Store the ACK

                         if ({swdi,rd[31:30]}==3'b001)               // Its a good one
                           begin
                              if (rnw)                          // ..and we're reading
                                begin
                                   bitcount  <= PROT_DATA;      // So straight to data
                                   swd_state <= ST_DATA;
                                end // if(rnw)
                              else
                                begin
                                   spincount <= turnaround;    // Otherwise, its write
                                   swd_state <= ST_TRN2;            // ..so turn again
                                end // else: !if(rnw)

                           end
                         else     // Wasn't good, give up and return idle, via cooloff
                           begin
                              bitcount  <= PROT_EOF;
                              spincount <= dataphase?33:2;           // Extended cool?
                              swd_state <= ST_COOLING;              // Go and cool off
                           end // else: !if({swdi,rd[31:30]}==3'b001)
                      end // if (bitcount==PROT_ACK_END)
                 end // case: ST_ACK

               ST_TRN2: // Turnaround for write time =================================
                 begin
                    spincount <= spincount - 1;              // Click through the turn
                    if (!spincount)
                      begin
                         bitcount  <= PROT_DATA;                  // If done then move
                         swd_state <= ST_DATA;                         // to dataphase
                      end // if (!spincout)
                 end // case: ST_TRN2

               ST_DATA: // Reading or writing 32 bit value ===========================
                 begin
                    bitcount<=bitcount+1;                    // Click through the data
                    par <= par ^ swdi;                            // Collecting parity
                    if (bitcount==PROT_PAR-1)            // (for both rx and tx cases)
                      dread     <= rd;                       // Store a completed read

                    if (bitcount==PROT_PAR)
                      begin
                         if (rnw)
                           begin
                              perr      <= par;                    // Report any error
                              swd_state <= ST_IDLE;                  // and we're done
                           end // if (rnw)
                         else
                           begin
                              spincount <= idleCycles+3;        // Always some cooling
                              swd_state <= ST_COOLING;             // on a write cycle
                           end // else: !if(rnw)
                      end // if (bitcount==PROT_PAR)
                 end // case: ST_DATA

               ST_COOLING: // Cooling the link before shutting it ====================
                 begin
                    spincount <= spincount-1;                // Click down the cooling
                    if (!spincount)
                      swd_state <= ST_IDLE;                   // ...and return to idle
                 end

               default: // Just in case ==============================================
                 swd_state <= ST_IDLE;                               // return to idle

             endcase // case (swd_state) =============================================
          end // if (rising)
     end // always @ (posedge clk)
endmodule // swdIF
