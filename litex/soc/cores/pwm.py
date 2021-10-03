#
# This file is part of LiteX.
#
# Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2019 Sean Cross <sean@xobs.io>
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause


from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *
from litex.soc.integration.doc import AutoDoc, ModuleDoc

# Timer --------------------------------------------------------------------------------------------

class PWM(Module, AutoCSR, AutoDoc):

    pads_layout = [("pwm_in", 1)]

    def __init__(self, width=32, pads=None):
        if pads is None:
            self.pads = Record(self.pads_layout)
        else:
            self.pads = pads

        self.intro = ModuleDoc("""Timer

    Provides a generic PWM input core.

    """)

        self._value = CSRStatus(width, description="""Latched countdown value.
            This value is updated by writing to ``update_value``.""")
        self._cycles = CSRStatus(width, description="""Latched countdown value.
            This value is updated by writing to ``update_value``.""")

        # # #

        self.pwm_in = Signal()

        pwm_in_d  = Signal()
        pwm_rise = Signal()
        pwm_fall = Signal()
        value = Signal(width)
        cycles = Signal(width)

        self.specials += [
            MultiReg(self.pads.pwm_in, self.pwm_in),
        ]
        
        self.sync += pwm_in_d.eq(self.pwm_in)
        self.comb += pwm_rise.eq(self.pwm_in & ~pwm_in_d)
        self.comb += pwm_fall.eq(~self.pwm_in & pwm_in_d)

        self.sync += [
            If(pwm_rise,
                self._cycles.status.eq(cycles),
                cycles.eq(0)
            ).Else(
                cycles.eq(cycles + 1)
            ),
            If(pwm_fall,
                self._value.status.eq(value),
                value.eq(0)
            ),
            If(self.pwm_in,
                value.eq(value + 1)
            )
        ]
