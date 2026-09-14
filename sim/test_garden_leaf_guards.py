#!/usr/bin/env python3
"""Keep leaf maintenance opt-in and unavailable in firmware."""
import argparse
import itertools
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent / "src"
    for leaf, combined, device in itertools.product((False, True), repeat=3):
        command = [args.cc, "-std=c11", "-Werror", "-fsyntax-only", "-I", str(source), "-xc", "-"]
        if leaf:
            command.append("-DTOY_FACTORY_GARDEN_LEAF_MAINTENANCE=1")
        if combined:
            command += ["-DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=1", "-DTOY_FACTORY_GARDEN_WATER_HEADROOM=1",
                        "-DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=1"]
        if device:
            command.append("-D__ZEPHYR__")
        result = subprocess.run(command, input='#include "garden_leaf.h"\n', text=True,
                                capture_output=True, timeout=30)
        expected = (not leaf or combined) and not (device and (leaf or combined))
        assert (result.returncode == 0) == expected, result.stderr
        result = subprocess.run(command, input='#include "garden_water_audit.h"\n', text=True,
                                capture_output=True, timeout=30)
        assert (result.returncode == 0) == (leaf and combined and not device), result.stderr
        result = subprocess.run(command, input='#include "garden_seed_audit.h"\n', text=True,
                                capture_output=True, timeout=30)
        assert (result.returncode == 0) == (leaf and combined and not device), result.stderr
        result = subprocess.run([*command,"-DTOY_FACTORY_GARDEN_BOTTOM_DRAINAGE=1"],
                                input='#include "garden_world.h"\n',text=True,capture_output=True,timeout=30)
        assert (result.returncode == 0) == (leaf and combined and not device), result.stderr
    for bank, leaf, pool, drainage, device in itertools.product((False, True), repeat=5):
        command = [args.cc, "-std=c11", "-Werror", "-fsyntax-only", "-I", str(source), "-xc", "-",
                   "-DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=1",
                   "-DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=1", "-DTOY_FACTORY_GARDEN_WATER_HEADROOM=1"]
        for yes, macro in ((bank, "TOY_FACTORY_GARDEN_LARGE_SEED_BANK"),
                           (leaf, "TOY_FACTORY_GARDEN_LEAF_MAINTENANCE"),
                           (pool, "TOY_FACTORY_GARDEN_LARGE_POOL"),
                           (drainage, "TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE"), (device, "__ZEPHYR__")):
            if yes:
                command.append("-D" + macro + "=1")
        expected = not device and (not drainage or leaf) and (not bank or (leaf and pool and not drainage))
        code = '#include "garden_world.h"\n_Static_assert(PICOSYSTEM_GARDEN_MAX_SEEDS == ' + (
            "16" if bank else "8") + ', "seed capacity");\n'
        result = subprocess.run(command, input=code, text=True, capture_output=True, timeout=30)
        assert (result.returncode == 0) == expected, result.stderr
    print("Host/device/opt-in leaf, audit and seed-bank guards passed")
    for leaf, pool, drainage, device in itertools.product((False, True), repeat=4):
        command = [args.cc, "-std=c11", "-Werror", "-fsyntax-only", "-I", str(source), "-xc", "-",
                   "-DTOY_FACTORY_GARDEN_SEED_RESERVE=1", "-DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=1",
                   "-DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=1", "-DTOY_FACTORY_GARDEN_WATER_HEADROOM=1"]
        for yes, macro in ((leaf, "TOY_FACTORY_GARDEN_LEAF_MAINTENANCE"),
                           (pool, "TOY_FACTORY_GARDEN_LARGE_POOL"),
                           (drainage, "TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE"), (device, "__ZEPHYR__")):
            if yes:
                command.append("-D" + macro + "=1")
        result = subprocess.run(command, input='#include "garden_seed_reserve.h"\n',
                                text=True, capture_output=True, timeout=30)
        assert (result.returncode == 0) == (leaf and pool and not drainage and not device), result.stderr
    print("Host/device/opt-in seed reserve guards passed")
    result = subprocess.run([args.cc, "-std=c11", "-Werror", "-fsyntax-only", "-I", str(source),
        "-D__ZEPHYR__", str(source.parent / "sim/garden_root_bootstrap.c")],
        text=True, capture_output=True, timeout=30)
    assert result.returncode != 0 and "Root bootstrap" in result.stderr
    print("Root bootstrap remains unavailable in firmware")
    result = subprocess.run([args.cc, "-std=c11", "-Werror", "-fsyntax-only", "-I", str(source),
        "-D__ZEPHYR__", str(source.parent / "sim/garden_allocation_policy.c")],
        text=True, capture_output=True, timeout=30)
    assert result.returncode != 0 and "Allocation routing" in result.stderr
    print("Allocation routing remains unavailable in firmware")


if __name__ == "__main__":
    main()
