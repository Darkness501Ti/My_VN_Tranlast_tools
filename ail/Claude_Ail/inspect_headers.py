"""Inspect Ail Soft engine file headers."""
import os
import struct

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"

files = ['sall.snl', 'Gall0.dat', 'Gall1.dat', 'Gall2.dat', 'Gall3.dat',
         'Pall0.dat', 'Pall1.dat', 'Pall2.dat',
         'vall00.dat', 'vall01.dat', 'vall08.dat',
         'THelp.dat', 'setup.lst']

for f in files:
    p = os.path.join(base, f)
    sz = os.path.getsize(p)
    with open(p, 'rb') as fp:
        head = fp.read(128)
    print(f"=== {f}  size={sz:,d}")
    print(f"  hex[0:64] : {head[:64].hex()}")
    print(f"  hex[64:128]: {head[64:128].hex()}")
    # try common little-endian header fields
    if sz >= 8:
        u32_0 = struct.unpack_from('<I', head, 0)[0]
        u32_4 = struct.unpack_from('<I', head, 4)[0]
        u32_8 = struct.unpack_from('<I', head, 8)[0]
        u32_12 = struct.unpack_from('<I', head, 12)[0]
        print(f"  u32[0..16]: {u32_0} {u32_4} {u32_8} {u32_12}")
    print()
