#
# This file is part of LiteX.
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 Dolu1990 <charles.papon.90@gmail.com>
# This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
# This file is Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
# This file is Copyright (c) 2019 Antmicro <www.antmicro.com>
# This file is Copyright (c) 2013 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2018 Sean Cross <sean@xobs.io>
# This file is Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
# This file is Copyright (c) 2018-2016 Tim 'mithro' Ansell <me@mith.ro>
# This file is Copyright (c) 2015 whitequark <whitequark@whitequark.org>
# This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2020 Piotr Esden-Tempski <piotr@esden.net>
# This file is Copyright (c) 2021 David Jablonski <dayjaby@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import json
import inspect
from shutil import which
from sysconfig import get_platform

from migen import *

from litex.soc.interconnect.csr import CSRStatus

from litex.build.tools import generated_banner

from litex.soc.doc.rst import reflow
from litex.soc.doc.module import gather_submodules, ModuleNotDocumented, DocumentedModule, DocumentedInterrupts
from litex.soc.doc.csr import DocumentedCSRRegion
from litex.soc.interconnect.csr import _CompoundCSR

# Jinja2 Environment --------------------------------------------------------------------------------

from jinja2 import Environment, FileSystemLoader

script_path = os.path.dirname(os.path.realpath(__file__))
jinja_env = Environment(
    loader=FileSystemLoader(os.path.join(script_path, 'templates')),
    trim_blocks=True,
    lstrip_blocks=True
)

def hex_zfill(v, size=None, upper=False):
    v = hex(v)
    if upper:
        v = v.upper()
    if size:
        v = "0x" + v[2:].zfill(size)
    return v

jinja_env.filters["hex"] = hex_zfill
jinja_env.filters["hasattr"] = hasattr
jinja_env.filters["reflow"] = reflow
jinja_env.filters["strip_eventmanager_field"] = lambda s: s[3:] if s.startswith("ev_") else s
jinja_env.globals["getattr"] = getattr
next_power_of_2 = lambda x, at_least=None: max([1<<(x-1).bit_length()] + ([at_least] if at_least else []))
jinja_env.globals["get_ctype"] = lambda size: "uint{}_t".format(next_power_of_2(size, at_least=8))

# CPU files ----------------------------------------------------------------------------------------

def get_cpu_mak(cpu, compile_software):
    # select between clang and gcc
    clang = os.getenv("CLANG", "")
    if clang != "":
        clang = bool(int(clang))
    else:
        clang = None
    if not hasattr(cpu, "clang_triple"):
        if clang:
            raise ValueError(cpu.name + "not supported with clang.")
        else:
            clang = False
    else:
        # Default to gcc unless told otherwise
        if clang is None:
            clang = False
    assert isinstance(clang, bool)
    if clang:
        triple = cpu.clang_triple
        flags = cpu.clang_flags
    else:
        triple = cpu.gcc_triple
        flags = cpu.gcc_flags

    # select triple when more than one
    def select_triple(triple):
        r = None
        if not isinstance(triple, tuple):
            triple = (triple,)
        override = os.getenv("LITEX_ENV_CC_TRIPLE")
        if override:
            triple = (override,) + triple
        p = get_platform()
        for i in range(len(triple)):
            t = triple[i]
            # use native toolchain if host and target platforms are the same
            if t == 'riscv64-unknown-elf' and p == 'linux-riscv64':
                r = '--native--'
                break
            if which(t+"-gcc"):
                r = t
                break
        if r is None:
            if not compile_software:
                return "--not-found--"
            msg = "Unable to find any of the cross compilation toolchains:\n"
            for i in range(len(triple)):
                msg += "- " + triple[i] + "\n"
            raise OSError(msg)
        return r

    # return informations
    return [
        ("TRIPLE", select_triple(triple)),
        ("CPU", cpu.name),
        ("CPUFLAGS", flags),
        ("CPUENDIANNESS", cpu.endianness),
        ("CLANG", str(int(clang))),
        ("CPU_DIRECTORY", os.path.dirname(inspect.getfile(cpu.__class__))),
    ]

def get_linker_output_format(cpu):
    return "OUTPUT_FORMAT(\"" + cpu.linker_output_format + "\")\n"

def get_linker_regions(regions):
    return jinja_env.get_template("regions.ld.jinja").render(
        regions=regions
    )

# C Export -----------------------------------------------------------------------------------------

def get_git_header():
    from litex.build.tools import get_migen_git_revision, get_litex_git_revision
    return jinja_env.get_template("git.h.jinja").render(
        generated_banner=generated_banner("//"),
        migen_git_revision=get_migen_git_revision(),
        litex_git_revision=get_litex_git_revision()
    )

def get_mem_header(regions):
    return jinja_env.get_template("mem.h.jinja").render(
        generated_banner=generated_banner("//"),
        regions=regions
    )

def get_soc_header(constants, with_access_functions=True):
    return jinja_env.get_template("soc.h.jinja").render(
        generated_banner=generated_banner("//"),
        constants=constants
    )

def get_csr_header(regions, constants, csr_base=None, with_access_functions=True):
    return jinja_env.get_template("csr.h.jinja").render(
        alignment=constants.get("CONFIG_CSR_ALIGNMENT", 32),
        generated_banner=generated_banner("//"),
        with_access_functions=with_access_functions,
        csr_base=csr_base if csr_base is not None else regions[next(iter(regions))].origin,
        regions=regions
    )

# JSON Export --------------------------------------------------------------------------------------

def get_csr_json(csr_regions={}, constants={}, mem_regions={}):
    alignment = constants.get("CONFIG_CSR_ALIGNMENT", 32)

    d = {
        "csr_bases":     {},
        "csr_registers": {},
        "constants":     {},
        "memories":      {},
    }

    for name, region in csr_regions.items():
        d["csr_bases"][name] = region.origin
        region_origin = region.origin
        if not isinstance(region.obj, Memory):
            for csr in region.obj:
                size = (csr.size + region.busword - 1)//region.busword
                d["csr_registers"][name + "_" + csr.name] = {
                    "addr": region_origin,
                    "size": size,
                    "type": "ro" if isinstance(csr, CSRStatus) else "rw"
                }
                region_origin += alignment//8*size

    for name, value in constants.items():
        d["constants"][name.lower()] = value.lower() if isinstance(value, str) else value

    for name, region in mem_regions.items():
        d["memories"][name.lower()] = {
            "base": region.origin,
            "size": region.length,
            "type": region.type,
        }

    return json.dumps(d, indent=4)


# CSV Export --------------------------------------------------------------------------------------

def get_csr_csv(csr_regions={}, constants={}, mem_regions={}):
    d = json.loads(get_csr_json(csr_regions, constants, mem_regions))
    r = generated_banner("#")
    for name, value in d["csr_bases"].items():
        r += "csr_base,{},0x{:08x},,\n".format(name, value)
    for name in d["csr_registers"].keys():
        r += "csr_register,{},0x{:08x},{},{}\n".format(name,
            d["csr_registers"][name]["addr"],
            d["csr_registers"][name]["size"],
            d["csr_registers"][name]["type"])
    for name, value in d["constants"].items():
        r += "constant,{},{},,\n".format(name, value)
    for name in d["memories"].keys():
        r += "memory_region,{},0x{:08x},{:d},{:s}\n".format(name,
            d["memories"][name]["base"],
            d["memories"][name]["size"],
            d["memories"][name]["type"],
            )
    return r

# SVD Export --------------------------------------------------------------------------------------

def get_csr_svd(soc, vendor="litex", name="soc", description=None):
    interrupts = {}
    for csr, irq in sorted(soc.irq.locs.items()):
        interrupts[csr] = irq

    documented_regions = []
    for region_name, region in soc.csr.regions.items():
        documented_regions.append(DocumentedCSRRegion(
            name           = region_name,
            region         = region,
            csr_data_width = soc.csr.data_width)
        )
    return jinja_env.get_template("csr.svd.jinja").render(
        soc=soc,
        vendor=vendor,
        name=name,
        description=description,
        interrupts=interrupts,
        documented_regions=documented_regions
    ).replace("__jinja2_newline__", "\n")

# Memory.x Export ----------------------------------------------------------------------------------

def get_memory_x(soc):
    return jinja_env.get_template("Memory.x.jinja").render(
        regions=soc.mem_regions,
        reset_address=soc.cpu.reset_address
    )
