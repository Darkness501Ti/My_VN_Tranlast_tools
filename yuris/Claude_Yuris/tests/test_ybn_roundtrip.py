"""Round-trip safety net: identity-edit (no string changes) MUST produce
byte-identical YBN. If this fails, the patcher is unsafe."""

import sys
import os
import glob
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from yuris_translate import extract_ypf, find_script_key, find_scripts_archive
from ybn_patcher import ybn_load_strings, ybn_patch_strings

JP = r"D:\game_install\501Translate\waiting to Tranlaste\JP"


def _roundtrip_one_game(game_name, exe_name):
    src_ypf = find_scripts_archive(os.path.join(JP, game_name))
    exe = os.path.join(JP, game_name, exe_name)
    script_key = find_script_key(exe)

    out = tempfile.mkdtemp(prefix=f"ybn_rt_{game_name[:4]}_")
    try:
        extract_ypf(src_ypf, out)
        # Only test yst[0-9]*.ybn — skip system files (ysc/ysv/ysl/yst_list/yst.ybn)
        ybns = sorted(
            glob.glob(os.path.join(out, "**", "yst[0-9]*.ybn"), recursive=True),
            key=os.path.getsize,
        )
        assert ybns, f"no yst*.ybn extracted for {game_name}"
        target = ybns[0]  # smallest for fast test

        with open(target, "rb") as f:
            original = f.read()

        strings = ybn_load_strings(original, script_key)
        rebuilt = ybn_patch_strings(original, script_key, strings)

        if rebuilt != original:
            first_diff = next(
                (i for i, (a, b) in enumerate(zip(original, rebuilt)) if a != b),
                -1,
            )
            raise AssertionError(
                f"round-trip not byte-equal for {os.path.basename(target)} "
                f"({game_name}): orig {len(original)}B vs new {len(rebuilt)}B; "
                f"first diff at byte {first_diff}"
            )
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_roundtrip_pleaserme():
    _roundtrip_one_game("Please R Me!", "prm.exe")


def test_roundtrip_terabeppin():
    _roundtrip_one_game("Tera Beppin", "terabeppin.exe")


def test_roundtrip_mousou():
    _roundtrip_one_game("Mousou Haruna-san", "Mousou.exe")
