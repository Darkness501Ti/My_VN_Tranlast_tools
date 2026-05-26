"""Inspect Thelp.dat and Ball.dat structure more thoroughly."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings

base = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\SAKURAKODL"

print("=== Thelp.dat (compare kouhouDL vs sakurakoDL) ===")
KOUHOU_THELP = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL\THelp.dat"
SAKURA_THELP = os.path.join(base, 'Thelp.dat')

for label, path in [('kouhouDL', KOUHOU_THELP), ('sakurakoDL', SAKURA_THELP)]:
    if not os.path.isfile(path):
        continue
    sz = os.path.getsize(path)
    print(f"\n--- {label}: {sz:,d} bytes")
    c, sizes, blobs = read_archive(path)
    print(f"    entries: {c}, nonzero: {sum(1 for s in sizes if s)}")
    # Inspect first few non-empty entries
    for i, b in enumerate(blobs[:6]):
        if not b: continue
        head = b[:32]
        # Check the LZSS magic
        u16 = struct.unpack_from('<H', b, 0)[0]
        u32_2 = struct.unpack_from('<I', b, 2)[0] if len(b) >= 6 else 0
        print(f"    entry {i}: size={len(b)}, u16@0={u16}, u32@2={u32_2}, head={head[:16].hex()}")
        if u16 == 1:
            try:
                payload, info = decode_entry(b)
                strs = extract_sjis_strings(payload, min_bytes=4)
                print(f"      decompressed: {len(payload)}B, {len(strs)} SJIS strings")
                for off, ln, s in strs[:3]:
                    print(f"        {s!r}")
            except Exception as e:
                print(f"      decode failed: {e}")

print("\n\n=== Ball.dat ===")
ball = os.path.join(base, 'Ball.dat')
c, sizes, blobs = read_archive(ball)
print(f"  count: {c}")
for i, b in enumerate(blobs):
    if not b:
        print(f"  entry {i}: EMPTY")
        continue
    u16 = struct.unpack_from('<H', b, 0)[0]
    head = b[:32].hex()
    print(f"  entry {i}: size={len(b):,d}, u16@0={u16}, head={head}")
    # Is it Ogg / WAV / video?
    if b[:4] == b'OggS' or b[4:8] == b'OggS':
        print(f"    -> contains Ogg")
    elif b[:4] == b'RIFF':
        print(f"    -> contains RIFF/WAV")
    elif b[:8] == b'\x89PNG\r\n\x1a\n':
        print(f"    -> contains PNG")
    elif b[:4] == b'\x30\x26\xb2\x75':
        print(f"    -> contains WMV/ASF")
