// JTAG-DP Interface
// From CoreSight TPIU-Lite Technical Reference Manual Revision: r0p0

`timescale 10ns/1ns

// Tests for jtagIF.
//
// Run with
//  iverilog -o r jtagIF.v ../testbeds/jtagIF_tb.v  ; vvp r
// Make -DSTATETRACE=1 for detail tracing inside swdIF.v.


module jtagIF_tb;


   // Testbed interface
   reg         rst_tb;
   reg         clk_tb;

   wire 	   tdo_tb;
   wire 	   tdi_tb;
   wire 	   tms_tb;
   wire        tck_tb;

   reg [1:0]   addr32_tb;
   reg         rnw_tb;
   reg         apndp_tb;
   reg [31:0]  dwrite_tb;
   wire [2:0]  ack_tb;
   wire [31:0] dread_tb;
   reg         go_tb;
   reg         jtagclk_in_tb;
   reg 		   old_jtagclk_in_tb;
   reg [7:0]   cnt;


   wire        done_tb;
   reg [1:0]   cmd_tb;

   reg [2:0]   dev_tb;
   reg [2:0]   ndevs_tb;
   reg [29:0]  irlenx_tb;


   reg [44:0]  rx;

   reg [2:0]   clkdiv;

   wire        anedge      = (old_jtagclk_in_tb^jtagclk_in_tb);
   wire        fallingedge = (anedge && ~jtagclk_in_tb);
   wire        risingedge = (anedge && jtagclk_in_tb);

   jtagIF DUT (
			   .rst(rst_tb),      // Reset synchronised to clock
			   .clk(clk_tb),

			   // Downwards interface to the JTAG pins
			   .tdo(tdo_tb),      // Test Data Out from targets
			   .tdi(tdi_tb),      // Test Data In to targets
			   .tms(tms_tb),      // Test Mode Select to targets
			   .tck(tck_tb),      // Test clock out to targets

                .dev(dev_tb),      // Device in chain we're talking to
                .ndevs(ndevs_tb),     // Number of devices in JTAG chain-1
                .irlenx(irlenx_tb),   // Length of each IR-1, 5x5 bits

			   .jtagclk_in(jtagclk_in_tb), // Input jtag clock
			   .falling(fallingedge),
			   .rising(risingedge),

			   // Upwards interface to command controller

               .cmd(cmd_tb),      // Command for JTAG IF to carry out
               .addr32(addr32_tb),   // Address bits 3:2 for message
               .rnw(rnw_tb),      // Set for read, clear for write
               .apndp(apndp_tb),    // AP(1) or DP(0) access?
               .dwrite(dwrite_tb),   // Most recent data from us
               .ack(ack_tb),      // Most recent ack status
               .dread(dread_tb),    // Data read from target

               .go(go_tb),       // Trigger
               .done(done_tb)    // Response
			   );


   integer c=0;

   always
	 while (1)
	   begin
          #1;
	      clk_tb=~clk_tb;
	   end

   always @(posedge tck_tb)
	 begin
		cnt<=cnt+1;
		$write("%3d %h %h %h\n",cnt,tms_tb,tdi_tb,tdo_tb);
	 end

   always @(negedge clk_tb)
	 begin
		clkdiv<=clkdiv-1;
		old_jtagclk_in_tb <= jtagclk_in_tb;
		if (!clkdiv)
		  jtagclk_in_tb <= ~jtagclk_in_tb;
	 end

   initial begin
      go_tb=0;
	  cnt=0;

	  jtagclk_in_tb=0;
	  cmd_tb=0;
	  clkdiv=0;
      rst_tb=0;
      clk_tb=0;
      #10;
      rst_tb=1;
      #10;
      rst_tb=0;
      #20;

      // =========================================== Reset TAPs


	  ndevs_tb <= 5;
	  dev_tb <= 1;
	  irlenx_tb = {5'd5,5'd1,5'd1,5'd7,5'd5,5'd1};
//      $display("\nCollect ID Data");
//	  cmd_tb <= 3; // JTAG_CMD_READID

//      go_tb <=1;
//      while (done_tb==1) #1;
//      go_tb <=0;
//      while (done_tb==0) #1;

//	  cmd_tb <= 0; // JTAG_CMD_IR
//	  dev_tb <= 1;
//	  dwrite_tb <= 32'hffff_ffff;

//      go_tb <=1;
//      while (done_tb==1) #1;
//      go_tb <=0;
//      while (done_tb==0) #1;

      $display("\nWrite location");
	  cmd_tb <= 1;  // JTAG_CMD_TFR
	  dev_tb <= 2;
	  addr32_tb <= 2'b11;

	  rnw_tb <= 0;

	  dwrite_tb <= 32'h80000002;


      go_tb <=1;
      while (done_tb==1) #1;
      go_tb <=0;
      while (done_tb==0) #1;



      $finish;
   end
   initial begin
      $dumpfile("jtag_IF.vcd");

      $dumpvars;
   end
endmodule // jtagIF_tb
