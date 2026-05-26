"""Test D: write archive with ORIGINAL LZSS bytes preserved (no recompression).

If this works in-game, then write_archive() is correct and my lzss_pack()
encoder is the broken piece. If this also fails, write_archive() has a bug.
"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, write_archive

JP_DIR = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
EN_DIR = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL_ENG_ver"

count, sizes, blobs = read_archive(os.path.join(JP_DIR, 'sall.snl'))

# Write back IDENTICAL data
out = os.path.join(EN_DIR, 'sall.snl')
write_archive(out, sizes, blobs)

# Verify byte-for-byte equality
import hashlib
with open(os.path.join(JP_DIR,'sall.snl'),'rb') as f: orig = f.read()
with open(out,'rb') as f: new  = f.read()
print(f"orig size: {len(orig):,d}")
print(f"new  size: {len(new):,d}")
print(f"sha256 orig: {hashlib.sha256(orig).hexdigest()}")
print(f"sha256 new : {hashlib.sha256(new).hexdigest()}")
print(f"BYTE-EQUAL: {orig == new}")
if orig != new:
    for i, (a, b) in enumerate(zip(orig, new)):
        if a != b:
            print(f"  first diff at byte {i}: orig=0x{a:02x} new=0x{b:02x}")
            break
print()
print(f"Now copy this file to install dir and test:")
print(f"  copy /Y \"{out}\" \"D:\\game_install\\501game\\Kouhou\\kouhouDL_game\\kouhouDL\\sall.snl\"")
