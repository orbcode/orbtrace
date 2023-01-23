`default_nettype none
//`define RESPECT_SYNC_TO

// traceIF
// =======
// Concatenates defined bus width input data from TRACEDATA using TRACECLK to bring it
// into 16 bit packets, which are stored in memory in a 8 packet Frame if they're not
// 'pass' cases. Also deals with top level sync. Above this level nothing needs to
// know how wide the tracebus actually is.
// 
// Working from CoreSight TPIU-Lite Technical Reference Manual Revision: r0p0

module traceIF # (parameter MAXBUSWIDTH = 4, SYNC_BITS=27) (
		input                   rst,              // Reset synchronised to clock

	// Downwards interface to the trace pins (1-n bits max, can be less)
		input [MAXBUSWIDTH-1:0] traceDina,        // Tracedata rising edge (LSB)
		input [MAXBUSWIDTH-1:0] traceDinb,        // Tracedata falling edge (MSB)
		input                   traceClkin,       // Tracedata clock... async to clk
		input [1:0]             width,            // Incoming Bus width
                                                          //  0..3 (1, 1, 2 & 4 bits)
        // DIAGNOSTIC
                output                  edgeOutput,

`ifdef RESPECT_SYNC_TO
        // Control downwards interface
                input                   ignoreSyncCount,  // Dont take account of sync bit
`endif

 	// Upwards interface to packet processor
		output reg              FrAvail,          // Toggling indicator frame ready
		output reg [127:0]      Frame,            // The last frame
		);		  
   
   // Internals =======================================================================

   // Frame maintenance
   reg [35:0] 	construct;                // Track of data being constructed
   reg [111:0]  cFrame;                   // Entire TPIU frame being constructed
   reg [2:0] 	remainingClocks;          // Number of elements remaining for word
   reg [2:0]    elemCount;                // Element we're currently waiting to store
   reg          isREsync;                 // Do we have RE (if true)  or FE sync?
`ifdef RESPECT_SYNC_TO
   reg [SYNC_BITS-1:0]   syncInd;         // Stretcher since last sync (~0.7s @ 96MHz)
`endif   
   // Flag indicating we've got a new full sync
   wire        REsyncPacket =            (construct[35 -: 32]==32'h7fff_ffff);
   wire        FEsyncPacket = (width==3)?(construct[31 -: 32]==32'h7fff_ffff):
                              (width==2)?(construct[33 -: 32]==32'h7fff_ffff):
                                         (construct[34 -: 32]==32'h7fff_ffff);

   // Pointer to where the output data word is in the construct frame
   wire [15:0] packet = isREsync?           construct[35 -: 16]:
                                 (width==3)?construct[31 -: 16]:
                                 (width==2)?construct[33 -: 16]:
                                            construct[34 -: 16];

   // DIAGNOSTIC - To be removed
   assign edgeOutput = !isREsync;

   // Lookup for packet width to clocks
   wire [2:0] packetClocks = (width==2'b11)?3'h1:(width==2'h2)?3'h3:3'h7;

   // ================== Input data against traceclock from target system =============
   always @(posedge traceClkin, posedge rst)
     begin
        // Default status bits
	if (!rst)
	  begin
             /* Roll constructed value along to accomodate new data for 4, 2 & 1 bits */
             case (width)
               2'b11: construct <= {traceDinb[3:0],traceDina[3:0],construct[35:8]};
               2'b10: construct <= {traceDinb[1:0],traceDina[1:0],construct[35:4]};
               default: construct <= {traceDinb[0],traceDina[0],construct[35:2]};
             endcase

             /* Remember which edge we're synced on */
             if (REsyncPacket) isREsync<=1;
             if (FEsyncPacket) isREsync<=0;

             // Code for establishing and maintaining sync ============================
             if ( REsyncPacket || FEsyncPacket )
               begin
`ifndef SYNTHESIS
                  $display("Got sync");
`endif
                  remainingClocks <= packetClocks; // We need to grab the whole packet
                  elemCount       <= ~0;           // erase any partial packet
`ifdef RESPECT_SYNC_TO
                  syncInd         <= ~0;           // ..and max the stretch count
`endif
               end
             else
               begin
	          // Deal with complete element reception =============================
`ifdef RESPECT_SYNC_TO
                  if (syncInd) syncInd <= syncInd - 1;
`endif
                  if (remainingClocks) remainingClocks <= remainingClocks - 1;
	          else
                    begin
                       remainingClocks <= packetClocks;

                       if (packet != 16'h7fff)
                         begin
`ifndef SYNTHESIS
                            $display("Got word: %04X",packet);
`endif
                            elemCount <= elemCount - 1;

                            /* Put this word to correct place in constructed frame */
`ifdef RESPECT_SYNC_TO
                            if ((ignoreSyncCount) || (syncInd!=0))
`endif			      
			      begin
				 case (elemCount)
                                   7: cFrame[111 -:16]<={packet[7:0],packet[15:8]};
                                   6: cFrame[ 95 -:16]<={packet[7:0],packet[15:8]};
                                   5: cFrame[ 79 -:16]<={packet[7:0],packet[15:8]};
                                   4: cFrame[ 63 -:16]<={packet[7:0],packet[15:8]};
                                   3: cFrame[ 47 -:16]<={packet[7:0],packet[15:8]};
                                   2: cFrame[ 31 -:16]<={packet[7:0],packet[15:8]};
                                   1: cFrame[ 15 -:16]<={packet[7:0],packet[15:8]};
                                   0:
                                     begin
`ifndef SYNTHESIS
					$display("Complete, sending (%d)",FrAvail);
`endif
					Frame <= {cFrame,{packet[7:0],packet[15:8]}};
					FrAvail <= !FrAvail;
                                     end
				 endcase // case (elemCount)
                              end // if ((~respectSyncCount) || (syncInd!=0))
                         end // if (packet != 16'h7fff)
                    end // else: !if(remainingClocks)
               end // else: !if (syncPacket)
          end // else: !if(rst)
     end // always @ (posedge traceClkin, posedge rst)
endmodule // traceIF
