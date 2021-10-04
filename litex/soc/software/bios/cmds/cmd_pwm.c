// SPDX-License-Identifier: BSD-Source-Code

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include <generated/csr.h>

#include "../command.h"
#include "../helpers.h"

/**
 * Command "pwm_read"
 *
 * Read PWM value and cycles
 *
 */
#ifdef CSR_PWM_BASE
static void pwm_read_handler(int nb_params, char **params)
{
	char *c;
	unsigned char channel;

	if (nb_params > 1) {
		printf("pwm_read [<channel>]");
		return;
	}

	channel = strtoul(params[0], &c, 0);
	if (*c != 0) {
		printf("Incorrect channel");
		return;
	}

	printf("PWM: Value: %d, cycles: %d\n", pwm_value_read(), pwm_cycles_read());
}
define_command(pwm_read, pwm_read_handler, "Read pwm", PWM_CMDS);
#endif
