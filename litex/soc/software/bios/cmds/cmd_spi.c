// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "spi_chip_select"
 *
 * SPI chip select
 *
 */
#if (defined CSR_SPI_MASTER_CS_ADDR && defined CSR_SPI_MASTER_CS_SIZE)
static void spi_chip_select_handler(int nb_params, char **params)
{
	char* c;
	uint32_t value;
	if (nb_params < 1) {
		printf("spi_chip_select <0(off)|1(chip 1)|2(chip 2)|...>");
		return;
	}
	value = strtoul(params[0], &c, 0);
	if (value > 0) {
		value = 1 << (value-1);
	}
	spi_master_cs_write(value);
}
define_command(spi_chip_select, spi_chip_select_handler, "SPI chip select", SPI_CMDS);
#endif
