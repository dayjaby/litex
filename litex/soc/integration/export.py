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

from litex.soc.doc.module import gather_submodules, ModuleNotDocumented, DocumentedModule, DocumentedInterrupts
from litex.soc.doc.csr import DocumentedCSRRegion
from litex.soc.interconnect.csr import _CompoundCSR

# for generating a timestamp in the description field, if none is otherwise given
import datetime
import time

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

def get_linker_regions(jinja_env, regions):
    return jinja_env.get_template("regions.ld.jinja").render(
        regions=regions
    )

# C Export -----------------------------------------------------------------------------------------

def get_git_header(jinja_env):
    from litex.build.tools import get_migen_git_revision, get_litex_git_revision
    return jinja_env.get_template("git.h.jinja").render(
        generated_banner=generated_banner("//"),
        migen_git_revision=get_migen_git_revision(),
        litex_git_revision=get_litex_git_revision()
    )

def get_mem_header(jinja_env, regions):
    return jinja_env.get_template("mem.h.jinja").render(
        generated_banner=generated_banner("//"),
        regions=regions
    )

def get_soc_header(jinja_env, constants, with_access_functions=True):
    return jinja_env.get_template("soc.h.jinja").render(
        generated_banner=generated_banner("//"),
        constants=constants
    )

def get_csr_header(jinja_env, regions, constants, csr_base=None, with_access_functions=True):
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

def get_csr_svd(jinja_env, soc, vendor="litex", name="soc", description=None):
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

    svd = []
    svd.append('<?xml version="1.0" encoding="utf-8"?>')
    svd.append('')
    svd.append('<device schemaVersion="1.1" xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" xs:noNamespaceSchemaLocation="CMSIS-SVD.xsd" >')
    svd.append('    <vendor>{}</vendor>'.format(vendor))
    svd.append('    <name>{}</name>'.format(name.upper()))
    if description is not None:
        svd.append('    <description><![CDATA[{}]]></description>'.format(reflow(description)))
    else:
        fmt = "%Y-%m-%d %H:%M:%S"
        build_time = datetime.datetime.fromtimestamp(time.time()).strftime(fmt)
        svd.append('    <description><![CDATA[{}]]></description>'.format(reflow("Litex SoC " + build_time)))
    svd.append('')
    svd.append('    <addressUnitBits>8</addressUnitBits>')
    svd.append('    <width>32</width>')
    svd.append('    <size>32</size>')
    svd.append('    <access>read-write</access>')
    svd.append('    <resetValue>0x00000000</resetValue>')
    svd.append('    <resetMask>0xFFFFFFFF</resetMask>')
    svd.append('')
    svd.append('    <peripherals>')

    for region in documented_regions:
        csr_address = 0
        svd.append('        <peripheral>')
        svd.append('            <name>{}</name>'.format(region.name.upper()))
        svd.append('            <baseAddress>0x{:08X}</baseAddress>'.format(region.origin))
        svd.append('            <groupName>{}</groupName>'.format(region.name.upper()))
        if len(region.sections) > 0:
            svd.append('            <description><![CDATA[{}]]></description>'.format(
                reflow(region.sections[0].body())))
        svd.append('            <registers>')
        for csr in region.csrs:
            description = None
            if hasattr(csr, "description"):
                description = csr.description
            if isinstance(csr, _CompoundCSR) and len(csr.simple_csrs) > 1:
                is_first = True
                for i in range(len(csr.simple_csrs)):
                    (start, length, name) = sub_csr_bit_range(
                        region.busword, csr, i)
                    if length > 0:
                        bits_str = "Bits {}-{} of `{}`.".format(
                            start, start+length, csr.name)
                    else:
                        bits_str = "Bit {} of `{}`.".format(
                            start, csr.name)
                    if is_first:
                        if description is not None:
                            print_svd_register(
                                csr.simple_csrs[i], csr_address, bits_str + " " + description, length, svd)
                        else:
                            print_svd_register(
                                csr.simple_csrs[i], csr_address, bits_str, length, svd)
                        is_first = False
                    else:
                        print_svd_register(
                            csr.simple_csrs[i], csr_address, bits_str, length, svd)
                    csr_address = csr_address + 4
            else:
                length = ((csr.size + region.busword - 1) //
                            region.busword) * region.busword
                print_svd_register(
                    csr, csr_address, description, length, svd)
                csr_address = csr_address + 4
        svd.append('            </registers>')
        svd.append('            <addressBlock>')
        svd.append('                <offset>0</offset>')
        svd.append('                <size>0x{:x}</size>'.format(csr_address))
        svd.append('                <usage>registers</usage>')
        svd.append('            </addressBlock>')
        if region.name in interrupts:
            svd.append('            <interrupt>')
            svd.append('                <name>{}</name>'.format(region.name))
            svd.append('                <value>{}</value>'.format(interrupts[region.name]))
            svd.append('            </interrupt>')
        svd.append('        </peripheral>')
    svd.append('    </peripherals>')
    svd.append('    <vendorExtensions>')

    if len(soc.mem_regions) > 0:
        svd.append('        <memoryRegions>')
        for region_name, region in soc.mem_regions.items():
            svd.append('            <memoryRegion>')
            svd.append('                <name>{}</name>'.format(region_name.upper()))
            svd.append('                <baseAddress>0x{:08X}</baseAddress>'.format(region.origin))
            svd.append('                <size>0x{:08X}</size>'.format(region.size))
            svd.append('            </memoryRegion>')
        svd.append('        </memoryRegions>')

    svd.append('        <constants>')
    for name, value in soc.constants.items():
        svd.append('            <constant name="{}" value="{}" />'.format(name, value))
    svd.append('        </constants>')

    svd.append('    </vendorExtensions>')
    svd.append('</device>')
    return "\n".join(svd)

# Memory.x Export ----------------------------------------------------------------------------------

def get_memory_x(jinja_env, soc):
    return jinja_env.get_template("Memory.x.jinja").render(
        regions=soc.mem_regions,
        reset_address=soc.cpu.reset_address
    )
