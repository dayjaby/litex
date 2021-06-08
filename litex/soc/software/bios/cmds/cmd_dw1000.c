// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <generated/csr.h>
#include <system.h>

#include "../command.h"
#include "../helpers.h"

static void dw_xfer(uint8_t* tx_buf, uint32_t tx_len, uint8_t* rx_buf, uint32_t rx_len)
{
	spi_master_control_length_write(8); // we always use 8bits for a byte
	uint32_t timeout = 500;
	spi_master_cs_write(1);
        busy_wait_us(500);
	/*
	spi_master_cs_write(0);
        busy_wait_us(100);
	spi_master_cs_write(1);
	*/
	for(int j=0; j<tx_len+rx_len; ++j)
	{
		if (j<tx_len) {
			spi_master_mosi_write(tx_buf[j]);
			printf("Send %02X\n", tx_buf[j]);
		} else {
			spi_master_mosi_write(0);
		}
		spi_master_control_start_write(1);
		// while(spi_master_status_done_read() != 0) {}
		// spi_master_control_start_write(0);
		while(spi_master_status_done_read() == 0) {}
		if (j>=tx_len) {
			rx_buf[j-tx_len] = spi_master_miso_read();
			printf("Received %02X\n", rx_buf[j-tx_len]);
		}
	}
	spi_master_cs_write(0);
}

/**
 * Command "dw_device_id"
 *
 * DW1000 Get Device Id
 *
 */
static void dw_device_id_handler(int nb_params, char **params)
{
	uint8_t tx_buf[1];
	uint8_t rx_buf[4];
	tx_buf[0] = 0x00;
	dw_xfer(tx_buf, sizeof(tx_buf), rx_buf, sizeof(rx_buf));
	printf("Device ID: %02X%02X%02X%02X\n", rx_buf[3], rx_buf[2], rx_buf[1], rx_buf[0]);
}
define_command(dw_device_id, dw_device_id_handler, "DW1000 Device Id", DW1000_CMDS);

/**
 * Command "dw_reset"
 *
 * DW1000 Perform hardware reset
 *
 */
static void dw_reset_handler(int nb_params, char **params)
{
	uint8_t tx_buf[1];
	uint8_t rx_buf[4];
	tx_buf[0] = 0x00;
	dw_xfer(tx_buf, sizeof(tx_buf), rx_buf, sizeof(rx_buf));
	printf("Device ID: %02X%02X%02X%02X\n", rx_buf[3], rx_buf[2], rx_buf[1], rx_buf[0]);
}
define_command(dw_reset, dw_reset_handler, "DW1000 Perform hardware reset", DW1000_CMDS);
