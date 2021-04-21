`default_nettype none

// swdIF
// =====
//
// Working from ARM Debug Interface Architecture Specification ADIv5.0 to ADIv5.2
// Modelled on structure from DAPLink implementation at https://github.com/ARMmbed/DAPLink
// which in Apache 2.0 Licence.
// This gateware uses (obviously!) uses no code from DAPLink and is under BSD licence.

module swdIF (
		input             rst,      // Reset synchronised to clock
                input             clk,

	// Downwards interface to the SWD pins
                input             swdi,     // DIO pin from target
                output reg        swdo,     // DIO pin to target
                input             falling,  // Flag indicating falling edge to target
                input             rising,   // Flag indicating rising edge to target
                output reg        swwr,     // Direction of DIO pin

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
output reg c,
                input             go,       // Trigger
                output            idle      // Response
		);

   // Internals =======================================================================
   reg [3:0]                      swd_state;   // current state of machine
   reg [2:0]                      ack_in;      // ack coming in from target
   reg [5:0]                      bitcount;    // Counter for bits being transferred
   reg [31:0]                     bits;        // The bits being transferred
   reg                            par;         // Parity construct

`ifdef STATETRACE
   reg [3:0]                      swd_state_change;
`endif

   parameter ST_IDLE         = 0;
   parameter ST_HDR_TX       = 1;
   parameter ST_TRN1         = 2;
   parameter ST_ACK          = 3;
   parameter ST_TRN2         = 4;
   parameter ST_DWRITE       = 5;
   parameter ST_DREAD        = 6;
   parameter ST_DREADPARITY  = 7;
   parameter ST_FINALTURN    = 8;
   parameter ST_COOLING      = 9;

   assign idle = (swd_state==ST_IDLE);     // Definition for idleness

   always @(posedge clk, posedge rst)
     begin
        // Default status bits
	if (rst)
	  begin
             swd_state <= ST_IDLE;
             swwr      <= 1;
c<=0;
	  end
	else
	  begin
`ifdef STATETRACE
             // Print out state changes for testbench purposes
             swd_state_change<=swd_state;
             if (swd_state_change!=swd_state)
               begin
                  $display("");
                  $write("ST_");
                  case (swd_state)
                    ST_IDLE:         $write("IDLE");
                    ST_HDR_TX:       $write("HDR_TX");
                    ST_TRN1:         $write("TRN1");
                    ST_ACK:          $write("ACK");
                    ST_TRN2:         $write("TRN2");
                    ST_DWRITE:       $write("DWRITE");
                    ST_DWRITEPARITY: $write("DWRITEPARITY");
                    ST_DREAD:        $write("DREAD");
                    ST_DREADPARITY:  $write("DREADPARITY");
                    ST_FINALTURN:    $write("FINALTURN");
                    ST_COOLING:      $write("COOLING");
                    default:         $write("UNKNOWN!!");
                  endcase // case (swd_state)
                  $write(":");
               end // if (swd_state_change!=swd_state)
`endif

             if (falling)
               case (swd_state)
                 ST_IDLE: // Idle waiting for something to happen =====================
                   if (go)
                     begin
c<=0;
                        // Request to start a transfer (the starting 1 goes straight to line)
                        bits <= { 1'b1, 1'b0, apndp^rnw^addr32[1]^addr32[0], addr32[1], addr32[0], rnw, apndp };
                        bitcount  <= 6'h7;      // 8 bits, 1 being sent already now
                        swdo      <= 1'b1;
                        swwr      <= 1'b1;
                        swd_state <= ST_HDR_TX; // Send the packet header
                        perr      <= 1'b0;      // Clear any previous error
                        par       <= 1'b0;      // and clear accumulated parity
                     end

                 ST_HDR_TX: // Sending the packet header ==============================
                   begin
                      bits     <= {1'b1,bits[31:1]};
                      swdo     <= bits[0];
                      bitcount <= bitcount-1;

                      if (bitcount==1)
                        begin
                           bitcount  <= turnaround+1;
                           swd_state <= ST_TRN1;
                        end
                   end

                 ST_TRN1: // Performing turnaround ====================================
                   begin
                      swwr      <= 0;
                      bitcount <= bitcount - 1;
                      if (bitcount==1)
                        begin
                           bitcount  <= 3;
                           swd_state <= ST_ACK;
                        end
                   end // if (fallingedge)

                 ST_ACK: // Collect the ack bits ======================================
                   begin
c<=swdi;
                      ack_in   <= {swdi,ack_in[2:1]};
                      bitcount <= bitcount-1;
                      if (bitcount==1)
                        begin
                           // Check what kind of ack we got
                           if ({swdi,ack_in[2:1]}==3'b001)
                             begin
                                if (rnw)
                                  begin
                                     bitcount  <= 32;
                                     swd_state <= ST_DREAD;
                                  end
                                else
                                  begin
                                     bitcount <= turnaround+2;
                                     swd_state <= ST_TRN2;
                                  end
                             end
                           else
                             begin
                                // Wasn't good, give up and return idle, via cooloff
                                swwr      <= 1'b1;
                                swdo      <= 0;
                                bitcount  <= dataphase?33:2;
                                swd_state <= ST_COOLING;
                             end // else: !if(ack_in==3'b001)
                        end // if (bitcount==1)
                   end // case: ST_ACK

                 ST_TRN2: // Turnaround for write time ================================
                   begin
                      // Data write includes the parity bit at the end
                      bitcount  <= 33;
                      bits      <= dwrite;
                      swd_state <= ST_DWRITE;
                   end

                 ST_DREAD: // Reading 32 bit value ====================================
                   begin
                      bits     <= {swdi,bits[31:1]};
                      par      <= par^swdi;
                      bitcount <= bitcount-1;
                      if (bitcount==1)
                        swd_state <= ST_DREADPARITY;
                   end

                 ST_DWRITE: // Writing 32 bit value ===================================
                   if (!bitcount)
                     begin
                        // This is the cycle after full word transmission
                        // Note the cooling is needed according to STM32F427 reference
                        // manual RM0090 Rev 19 Section 38.8.4. Thanks guys, well hidden.
                        swdo <= 0;
                        bitcount <= idleCycles+3;
                        swd_state <= ST_COOLING;
                     end
                   else
                     begin
                        swwr     <= 1;
                        bits     <= {1'b0,bits[31:1]};
                        swdo     <= (bitcount==1)?par:bits[0];
                        par      <= par+bits[0];
                        bitcount <= bitcount-1;
                     end

                 ST_DREADPARITY: // Reading parity ====================================
                   begin
                      perr      <= par^swdi;
                      bitcount  <= 1;
                      swd_state <= ST_FINALTURN;
                   end

                 ST_FINALTURN: // Return to driven line =================================
                   begin
                      bitcount  <= bitcount-1;
                      if (!bitcount)
                        begin
                           swdo      <= 0;
                           bitcount  <= idleCycles;
                           if (idleCycles)
                             begin
                                swwr <= 1;
                                swd_state <= ST_COOLING;
                             end
                           else
                             begin
                                swwr <= 0;
                                swd_state <= ST_IDLE;
                             end
                        end
                   end

                 ST_COOLING: // Cooling the link before shutting it ===================
                   begin
                      bitcount  <= bitcount-1;
                      if (bitcount==1)
                        begin
                           ack       <= ack_in;
                           dread     <= bits;
                           swwr      <= 0;
                           swd_state <= ST_IDLE;
                        end
                   end
             endcase // case (swd_state)
          end // else: !if(rst)
     end // always @ (posedge clk, posedge rst)
endmodule // swdIF
