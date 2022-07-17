`default_nettype none
//
// SPDX-License-Identifier: BSD-3-Clause
//
// jtagIF
// ======
//
// Working from ARM Debug Interface Architecture Specification ADIv5.0 to ADIv5.2
// Timing is compliant to Section 3.3 (Pg 3.6) of ARM DUI 0517H which specifies
// TCK Low and High 50ns-500us. TDO to TCK rising setup min of 15ns, TDO hold of 5ns min,
// TDI and TMS valid for minimum of 6ns from TCK falling.
// Modelled on structure from DAPLink implementation at
// // https://github.com/ARMmbed/DAPLink which in Apache 2.0 Licence.
// This gateware uses (obviously!) uses no code from DAPLink and is under BSD licence.
//

module jtagIF (
	input 		          rst,                                       // Reset synchronised to clock
        input 			  clk,

	// Downwards interface to the JTAG pins ===========================================================
        input 			  tdo,                                        // Test Data Out from targets
        output reg 		  tdi,                                           // Test Data In to targets
        output reg 		  tms,                                       // Test Mode Select to targets
        output   	          tck,                                         // Test clock out to targets

	// Upwards interface to command controller ========================================================
        input [2:0] 	          dev,                                  // Device in chain we're talking to
        input [2:0] 	          ndevs,                               // Number of devices in JTAG chain-1
        input [29:0] 	          irlenx,                                  // Length of each IR-1, 6x5 bits
        input [3:0]               ir,                                                  // ARM JTAG IR value

        input 			  falling,                        // Flag indicating falling edge to target
        input 			  rising,                          // Flag indicating rising edge to target
        input 			  jtagclk_in,                                           // Input jtag clock

        input [1:0] 	          cmd,                                  // Command for JTAG IF to carry out
        input [1:0] 	          addr32,                                   // Address bits 3:2 for message
        input 			  rnw,                                     // Set for read, clear for write
        input 			  apndp,                                          // AP(1) or DP(0) access?
        input [31:0] 	          dwrite,                                       // Most recent data from us
        output reg [2:0]          ack,                                            // Most recent ack status
        output reg [31:0]         dread,                                           // Data read from target

        input 			  go,                                                            // Trigger
        output 			  idle                                                          // Response
		);

   // Internals ===========================================================================================
   reg [3:0]                      jtag_state;                                   // current state of machine
   reg [3:0]                      next_state;                       // State to switch to after current one
   reg [5:0]                      tmsbits;                                    // Number of TMS bits to send
   reg [4:0]                      windex;                                // Index into bit sequences in/out
   reg [2:0]                      tmscount;                              // Counter for tms bits being sent
   reg [5:0]                      tdxcount;                      // Counter for data bits being transferred
   reg [2:0]                      devcount;                       // Counter for number of devices in chain

   // Commands from layer above
   parameter JTAG_CMD_IR     = 0;                        // Set IR
   parameter JTAG_CMD_TFR    = 1;              // Perform transfer
   parameter JTAG_CMD_READID = 2;                  // Read ID Code
   parameter JTAG_CMD_RESET  = 3;      // Reset JTAG state machine

   // States for the machine
   parameter ST_JTAG_IDLE        = 0;        // Not doing anything
   parameter ST_JTAG_TMSOUT      = 1;     // Clocking out TMS bits
   parameter ST_JTAG_READID_DONE = 2;       // Finished reading ID
   parameter ST_JTAG_IDDATA      = 3;           // Getting ID data
   parameter ST_JTAG_WRITEIR     = 5;                // Writing IR
   parameter ST_JTAG_TRANSFER    = 6;  // Performing Data Transfer
   
   assign idle      = (jtag_state==ST_JTAG_IDLE);

// ========================================================================================================
`ifndef SYNTHESIS // ======================================================================================
   reg [3:0] 			  stateCopy;

   always @(posedge clk)
	 begin
		stateCopy <= jtag_state;

		if (stateCopy!=jtag_state)
		  case (jtag_state)
			ST_JTAG_IDLE:
			  $display("ST_JTAG_IDLE:");
			ST_JTAG_TMSOUT:
			  $display("ST_JTAG_TMSOUT:");
			ST_JTAG_READID_DONE:
			  $display("ST_JTAG_READID_DONE:");
			ST_JTAG_IDDATA:
			  $display("ST_JTAG_IDDATA:");
			ST_JTAG_WRITEIR:
			  $display("ST_JTAG_WRITEIR:");
			ST_JTAG_TRANSFER:
			  $display("ST_JTAG_TRANSFER:");
		  endcase // case (jtag_state)
	 end
`endif // =================================================================================================

   assign tck = (idle)?1'b1:jtagclk_in;

   always @(posedge clk)
     begin
        case (jtag_state)
	  // ==============================================================================================
          ST_JTAG_IDLE: // Idle waiting for something to happen ===========================================
            begin
	       tdxcount <= 0;
	       devcount <= 0;
               if (go & rising)              // Request to start a transfer
                 begin
		    jtag_state <= ST_JTAG_TMSOUT;
                    case (cmd)
                      JTAG_CMD_TFR: // Perform Transfer ---------------------------------------------------
			begin
			   tmsbits <= 6'b000100;
			   tmscount <= 3;
			   next_state <= ST_JTAG_TRANSFER;
			end
                      JTAG_CMD_READID:  // Read device id -------------------------------------------------
                        begin
                           tmsbits <=  6'b000100;
                           tmscount <= 4;
                           next_state <= ST_JTAG_IDDATA;
                        end
                      JTAG_CMD_IR: // Set IR --------------------------------------------------------------
                        begin
                           tmsbits <=  6'b0001100;
                           tmscount <= 4;
                           next_state <= ST_JTAG_WRITEIR;
                        end
                      JTAG_CMD_RESET: // Reset JTAG State Machine -----------------------------------------
                        begin
                           tmsbits <= 6'b111110;
                           tmscount <= 6;
                           next_state <= ST_JTAG_IDLE;
                        end
                    endcase // case (cmd)
                 end
            end // case: ST_JTAG_IDLE
	  
	  // ==============================================================================================
	  ST_JTAG_TRANSFER: // TRANSFER Supporting State ==================================================
	    begin
	       // Default action for ACK failure case (longest path, so do it here)
	       tmsbits    <= 6'b000100; // 6'b000001;
	       tmscount   <= 3;
	       next_state <= ST_JTAG_IDLE;
	       
	       if (falling) // Write Host -> Device -------------------------------------------------------
		 begin
		    if (devcount!=dev)
		      tdi<=1'b1;
		    else
		      case (tdxcount)
			0: tdi<=rnw;
			1: tdi<=addr32[0];
			2: tdi<=addr32[1];
			
			default:
			  tdi <= rnw?1'b1:dwrite[windex];
		      endcase // case (tdxcount)
		    
		    if ((devcount==ndevs))
		      tms      <= 1'b1;
		 end
	       
	       if (rising)  // Read Device -> Host --------------------------------------------------------
		 begin
		    tdxcount <= tdxcount+1;
		    windex   <= windex+1;
		    
		    case (tdxcount)
		      0: ack[0]<=tdo;
		      1: ack[1]<=tdo;
		      2: 
			begin
			   ack[2]<=tdo;
			   windex<=0;
			   
			   // If ack is wait then abort
			   if ({tdo,ack[1],ack[0]}!=2)
			     begin
				tmsbits <= 6'b000110;
				jtag_state <= ST_JTAG_TMSOUT;
			     end
			end
		      default: dread[windex] <= tdo;
		    endcase // case (tdxcount)
		    
		    // In bypass for every device except the target, so only 1 bit
		    if ((devcount!=dev) || (34==tdxcount))
		      begin
			 if (devcount==ndevs)
			      jtag_state <= ST_JTAG_TMSOUT;
			 else
			   begin
			      devcount <= devcount + 1;
			      tdxcount <= 0;
			   end
		      end
		 end // if (rising)
	    end
	  
	  // ==============================================================================================
          ST_JTAG_IDDATA: // READID Supporting States =====================================================
	    begin
	       if (falling)
		 tdi <= ((devcount==dev) & (rnw==0))?dwrite[tdxcount]:1'b0;
	       
	       if (rising)
		 begin
		    tdxcount <= tdxcount+1;
		    dread[tdxcount] <= tdo;
		    
		    // For ID read it's always 32 bits...
		    if (5'h1f==tdxcount)
		      begin
			 if (devcount==ndevs)
			   jtag_state <= ST_JTAG_READID_DONE;
			 else
			   begin
			      devcount <= devcount + 1;
			      tdxcount <= 0;
			   end
		      end
                 end
            end // case: ST_JTAG_IDDATA

	  // -----------------------------------------------------------------------
          ST_JTAG_READID_DONE: // Finished ID read, so return idle -----------------
	    begin
               next_state <= ST_JTAG_IDLE;
               tmsbits  <= 6'b000110;
	       tmscount <= 3;
	       if (falling)
                 jtag_state <= ST_JTAG_TMSOUT;
            end
	  
	  // ==============================================================================================
	  ST_JTAG_WRITEIR: // SETIR Supporting states =====================================================
	    begin
	       tmsbits <= 6'b000010;
	       tmscount <= 2;
	       next_state <= ST_JTAG_IDLE;

	       if (falling)
		 begin
		    tdi <= (devcount==dev)?ir[tdxcount]:1'b1;
		    
		    // If we are on the last bit then signal tms to leave
		    if ((devcount==ndevs) && (tdxcount[4:0]+1 == irlenx[ 5*devcount +:5 ] ))
		      tms <= 1'b1;
		 end
	       
	       if (rising)
		 begin
		    tdxcount <= tdxcount+1;
		    
		    if ( tdxcount[4:0]+1 == irlenx[ 5*devcount +:5 ] )
		      
		      begin
			 if (devcount==ndevs)
			   jtag_state <= ST_JTAG_TMSOUT;
			 else
			   begin
			      devcount <= devcount + 1;
			      tdxcount <= 0;
			   end
		      end
		 end
            end // case: ST_JTAG_WRITEIR
	  
	  // ==============================================================================================
          ST_JTAG_TMSOUT: // clock out defined tms bits ===================================================
	    begin
	       if (falling)
		 begin
		    tmscount <= tmscount-1;
		    tms      <= tmsbits[tmscount-1];
		 end
	       if (rising)
		 begin
		    if (tmscount==0)
		      jtag_state <= next_state;
		 end
	    end
        endcase // case (jtag_state)
     end // always @ (posedge clk)
endmodule // jtagIF

