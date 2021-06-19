#include <stdio.h>
#include <stdint.h>

//#include "include/time.h"
#include "hyperram.h"

#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/git.h>

#include <system.h>

#include <bios/init.h>

#ifdef CSR_HYPERRAM_BASE

/* Prototypes */

void set_io_delay(int);
void set_clk_delay(int);
static int basic_memtest(void);


void set_io_delay(int cnt){
	hyperram_io_loadn_write(0);
	hyperram_io_loadn_write(1);
	hyperram_io_direction_write(0);

	/* 25ps of delay per tap.
	   Each rising edge adds to the io delay */
	for(int i = 0; i < cnt; i++){ 
		hyperram_io_move_write(1);
		hyperram_io_move_write(0);
	}
}

void set_clk_delay(int cnt){
	hyperram_clk_loadn_write(0);
	hyperram_clk_loadn_write(1);
	hyperram_clk_direction_write(0);

	/* 25ps of delay per tap.
	   Each rising edge adds to the io delay */
	for(int i = 0; i < cnt; i++){ 
		hyperram_clk_move_write(1);
		hyperram_clk_move_write(0);
	}
}



/* 
	Test memory location by writing a value and attempting read-back.
	Try twice to avoid situation where memory is read-only and set from a previous test.
*/
static int basic_memtest(void){

	*((volatile uint32_t*)HYPERRAM_BASE) = 0xFF55AACD;

    flush_l2_cache();
    flush_cpu_dcache();

	if(*((volatile uint32_t*)HYPERRAM_BASE) != 0xFF55AACD)
		return 0;
//
	*((volatile uint32_t*)HYPERRAM_BASE) = 0xA3112233;

    flush_l2_cache();
    flush_cpu_dcache();

	if(*((volatile uint32_t*)HYPERRAM_BASE) != 0xA3112233)
		return 0;
	
	return 1;
}


void hyperram_init(void){
    printf("--==========-- \e[1mHyperRAM Init\e[0m ===========--\n");

	int window = 0;
	int clk_del = 0;
	int io_del = 0;

	while(clk_del < 128){
		set_clk_delay(clk_del >> 2);
		set_io_delay(io_del);
		int i = 0;
		printf("%u,%u, %u |", clk_del >> 2, clk_del & 1 ? 1 : 0, clk_del & 2 ? 1 : 0);
		for(i = 0; i < 64; i++){

			int pass = basic_memtest();

			// Shift our PLL
			crg_phase_sel_write(0);
			crg_phase_dir_write(0);
			crg_phase_step_write(0);
			crg_phase_step_write(1);

			if(i & 1)
				printf("%c", pass > 0 ? '0' : '-');

			if(pass == 1){
				window++;
			}
			else if(pass != 1){
				if(window >= 6){
					break;
				}else {
					window = 0;
				}
			}

		}
		printf("| %d    \n", window );
		if(window >= 5){
			for(i = 0; i < window/2; i++){
				// Shift our PLL up
				crg_phase_sel_write(0);
				crg_phase_dir_write(1);
				crg_phase_step_write(0);
				crg_phase_step_write(1);
			}
			return;
		}
		window = 0;
		clk_del = (clk_del + 1);

		crg_slip_hr2x90_write(clk_del & 1 ? 1 : 0);
		crg_slip_hr2x_write(clk_del & 2 ? 1 : 0);

		crg_slip_hr2x90_write(0);
		crg_slip_hr2x_write(0);
	}

	printf("\n\n Error: RAM Init failed :(\n Restarting in... ");
	for(int i = 0; i < 5; i++){
		//msleep(1000);
		printf("\b%u",5-i);
	}

	while(1){
		//reboot_ctrl_write(0xac);
	}
	
}

define_init_func(hyperram_init);

#else


void hyperram_init(){
	return;
}

#endif
