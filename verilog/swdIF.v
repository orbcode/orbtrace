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
                input             rst,                  // Reset synchronised to clock
                input             clk,

	// Downwards interface to the SWD pins
                input             swdi,                         // DIO pin from target
                output            swdo,                           // DIO pin to target
                input             falling,   // Flag indicating falling edge to target
                input             rising,     // Flag indicating rising edge to target
                input             swclk_in,                           // Input swclock
                output            swclk_out,                              // swclk out
                output            swwr,                        // Direction of DIO pin

        // Configuration
                input [1:0]       turnaround,            // Clock ticks per turnaround
                input             dataphase,    // Does a dataphase follow WAIT/FAULT?
                input [7:0]       idleCycles,          // How many idlecycles to apply

	// Upwards interface to command controller
                input [1:0]       addr32,              // Address bits 3:2 for message
                input             rnw,                // Set for read, clear for write
                input             apndp,                     // AP(1) or DP(0) access?
                input [31:0]      dwrite,                  // Most recent data from us
                output reg [2:0]  ack,                       // Most recent ack status
                output reg [31:0] dread,                      // Data read from target
                output reg        perr,                 // Indicator of a parity error
                input             go,                                       // Trigger
                output            idle                                     // Response
		);

   // Internals ======================================================================
   reg [2:0]                      swd_state;               // current state of machine

   reg [7:0]                      spincount;     // Counter for additional turn cycles

   reg [5:0]                      bitcount;      // Counter for bits being transferred
   reg                            par;                             // Parity construct
   reg [31:0]                     rd;       // The read data being prepared for return

   // States of the reception process
   parameter ST_IDLE         = 0;
   parameter ST_LINE_PREPARE = 1;
   parameter ST_HDR_TX       = 2;
   parameter ST_TRN1         = 3;
   parameter ST_ACK          = 4;
   parameter ST_TRN2         = 5;
   parameter ST_DATA         = 6;
   parameter ST_COOLING      = 7;

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
   assign swdo      = (idle || (bitcount==PROT_EOF) || (swd_state==ST_LINE_PREPARE))?0:bits[bitcount];
   assign swclk_out = (idle || (swd_state==ST_LINE_PREPARE))?1:swclk_in;
   assign swwr      = (
                       ((swd_state!=ST_IDLE) && (bitcount<PROT_TRN1)) ||     // Header
                       ((~rnw) && (bitcount>PROT_TRN2) ||     // Writing Data & Parity
			(bitcount>PROT_PAR))              // End of the frame, cooling
                      );

   always @(posedge clk)
     begin
        if (rising)
          begin
             rd  <= { swdi, rd[31:1] };     // Keep a sliding frame under construction
             bitcount <= (bitcount!=PROT_EOF)?bitcount+1:bitcount;          // Next bit

             case (swd_state)
               ST_IDLE: // Idle waiting for something to happen ======================
                 begin
                    if (go)                             // Request to start a transfer
                      begin
                         bitcount  <= 0;                  // Index through the tx bits
			 swd_state <= ST_HDR_TX;         // Ensures a stable 0 on line
                         perr      <= 0;                   // Clear any previous error
                         par       <= 0;               // and clear accumulated parity
                      end // if (go)
                 end

	       ST_LINE_PREPARE: // Extra bit time to establish SWD<=0 ================
		 begin
		    bitcount  <= 0;
		    swd_state <= ST_HDR_TX;                  // Send the packet header
		 end

               ST_HDR_TX: // Sending the packet header ===============================
                 begin
                    if (bitcount==PROT_HEAD_END)                    // Finished header
                      begin
                         spincount  <= turnaround;           // Number of bits of turn
			 swd_state  <= ST_TRN1;              // ...and move to do turn
                      end
                 end

               ST_TRN1: // Performing turnaround =====================================
                 begin
                    spincount<=spincount-1;                        // Turn in progress

		    // Note we're not using 'bitcount' in this state
                    if (!spincount)
		      begin
			 bitcount  <= PROT_ACK;         // ... and leave the TRN state
			 swd_state <= ST_ACK;                 // .. go collect the ACK
		      end
                 end

               ST_ACK: // Collect the ack bits =======================================
                 begin
                    if (bitcount==PROT_ACK_END)                       // Have now done
                      begin
                         ack <= {swdi,rd[31:30]};                     // Store the ACK
			 if ({swdi,rd[31:30]}==3'b001)               // Its a good one
                           begin
                              if (rnw)                          // ..and we're reading
				begin
				   bitcount <= PROT_DATA;
                                   swd_state <= ST_DATA;
				end
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
		    bitcount  <= PROT_DATA;                 // ...and collect databits

                    if (!spincount)
		      swd_state <= ST_DATA;                            // to dataphase
                 end // case: ST_TRN2

               ST_DATA: // Reading or writing 32 bit value ===========================
                 begin
                    par <= par ^ swdi;                            // Collecting parity
                    if (rnw & (bitcount==PROT_PAR-1))
		      dread     <= rd;                       // Store a completed read

		    if (bitcount==PROT_PAR)
                      begin
                         if (rnw)
			   perr    <= par;                         // Report any error
                         spincount <= rnw?turnaround:idleCycles;
                         swd_state <= ST_COOLING;
		      end
                 end // case: ST_DATA

               ST_COOLING: // Cooling the link before shutting it ====================
                 begin
                    spincount <= spincount-1;                // Click down the cooling
                    if (!spincount)
                      swd_state <= ST_IDLE;                   // ...and return to idle
                 end

             endcase // case (swd_state) =============================================
          end // if (rising)
     end // always @ (posedge clk)
endmodule // swdIF
