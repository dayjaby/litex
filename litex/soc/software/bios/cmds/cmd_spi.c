// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"

#if (defined CSR_SPI_MASTER_CS_ADDR && defined CSR_SPI_MASTER_CS_SIZE)
/**
 * Command "spi_chip_select"
 *
 * SPI chip select
 *
 */
static void spi_chip_select_handler(int nb_params, char **params)
{
	char* c;
	uint32_t value;
	if (nb_params < 1) {
		printf("spi_chip_select <0 (off) | 1 (chip 1) | 2 (chip 2) | ...>");
		return;
	}
	value = strtoul(params[0], &c, 0);
	if (value > 0) {
		value = 1 << (value-1);
	}
	spi_master_cs_write(value);
}
define_command(spi_chip_select, spi_chip_select_handler, "SPI chip select", SPI_CMDS);

#if (defined CSR_SPI_MASTER_LOOPBACK_ADDR && defined CSR_SPI_MASTER_LOOPBACK_SIZE)
/**
 * Command "spi_loopback"
 *
 * Enable/disable SPI MOSI to MISO loopback
 *
 */
static void spi_loopback_handler(int nb_params, char **params)
{
	char* c;
	uint32_t value;
	if (nb_params == 1)
	{
		value = strtoul(params[0], &c, 0);
		if (value == 0 || value == 1) 
		{
			spi_master_loopback_write(value);
			return;
		}
	}
	printf("spi_loopback <0 (off) | 1 (on)>");
	return;
}
define_command(spi_loopback, spi_loopback_handler, "SPI loopback enable/disable", SPI_CMDS);
#endif

/**
 * Command "spi_xfer"
 *
 * SPI transfer bytes
 *
 */
static void spi_xfer_handler(int nb_params, char **params)
{
	spi_master_control_length_write(8); // we always use 8bits for a byte
	for(int i=0; i<nb_params; ++i) 
	{
		uint32_t len = strlen(params[i]);
		for(int j=0; j<len; ++j)
		{
			spi_master_mosi_write((uint8_t)params[i][j]);
			spi_master_control_start_write(1);
			while(spi_master_status_done_read() == 0) {}
			uint8_t byte = (uint8_t)spi_master_miso_read();
			printf("Received %02X\n", byte);
		}
	}
}
define_command(spi_xfer, spi_xfer_handler, "SPI transfer bytes", SPI_CMDS);

#endif
