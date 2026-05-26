"""Diagnose why game still shows JP after sall.snl patch.

Checks:
  1. .exe size & whether it contains the same JP strings (embedded script)
  2. .exe contains references to sall.snl
  3. Patched sall.snl is valid (re-decompress all entries)
  4. Any other files in game dir that contain SJIS dialogue we missed
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings

JP_DIR = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
EN_DIR = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL_ENG_ver"

# 1. List file sizes
print("=== File sizes ===")
for name in os.listdir(JP_DIR):
    p = os.path.join(JP_DIR, name)
    if os.path.isfile(p):
        print(f"  {name:25s} {os.path.getsize(p):>14,d}")

# 2. Check exe for embedded JP text
print("\n=== Hunting JP/SJIS strings in kouhouDL.exe ===")
exe_path = os.path.join(JP_DIR, 'kouhouDL.exe')
with open(exe_path, 'rb') as f:
    exe = f.read()
print(f"  exe size: {len(exe):,d}")

# Look for any SJIS hiragana-rich runs
strs = extract_sjis_strings(exe, min_bytes=10)
print(f"  total SJIS strings >=5 chars: {len(strs)}")
for off, ln, s in strs[:15]:
    print(f"    @0x{off:06x} [{ln}B] {s!r}")

# 3. Check whether sall.snl is referenced in exe
print(f"\n=== Strings 'sall.snl' / 'sall' in exe ===")
for kw in [b'sall.snl', b'sall', b'.snl', b'Gall', b'Pall', b'vall']:
    idx = exe.find(kw)
    print(f"  {kw!r:15s}: {'found at 0x%x' % idx if idx>=0 else 'NOT FOUND'}")

# 4. Verify patched sall.snl is loadable
print(f"\n=== Verify patched sall.snl is well-formed ===")
patched = os.path.join(EN_DIR, 'sall.snl')
if not os.path.isfile(patched):
    print(f"  [!] {patched} doesn't exist!")
else:
    print(f"  patched size: {os.path.getsize(patched):,d}")
    count, sizes, blobs = read_archive(patched)
    print(f"  count: {count}, nonzero: {sum(1 for s in sizes if s)}")
    fail = 0
    for idx, blob in enumerate(blobs):
        if not blob: continue
        try:
            p, info = decode_entry(blob)
        except Exception as e:
            print(f"  ✗ entry {idx}: {e}")
            fail += 1
    if fail == 0:
        print(f"  all entries decode cleanly ✓")
    # Verify entry 0 (menu) shows English now
    payload, _ = decode_entry(blobs[0])
    strs0 = []
    i = 0
    while i < len(payload):
        if 0x20 <= payload[i] <= 0x7E and i+10 < len(payload):
            # try ASCII run
            j = i
            while j < len(payload) and 0x20 <= payload[j] <= 0x7E:
                j += 1
            if j - i >= 8:
                strs0.append((i, payload[i:j].decode('ascii', errors='replace')))
            i = j
        else:
            i += 1
    print(f"\n  patched entry 0 ASCII runs (should be English menu):")
    for off, s in strs0[:8]:
        print(f"    @0x{off:04x} {s!r}")

# 5. Look for any other file with SJIS dialogue
print(f"\n=== Other game files with embedded SJIS dialogue ===")
for name in os.listdir(JP_DIR):
    p = os.path.join(JP_DIR, name)
    if not os.path.isfile(p): continue
    if name in ('sall.snl',): continue
    if name.endswith('.wav'): continue
    if name.endswith('.dat'): continue  # already known graphics
    with open(p, 'rb') as f:
        data = f.read(min(os.path.getsize(p), 2_000_000))
    s = extract_sjis_strings(data, min_bytes=8)
    if s:
        print(f"  {name}: {len(s)} SJIS strings >=4 chars found")
        for off, ln, t in s[:3]:
            print(f"    @0x{off:06x} {t!r}")

# 6. Show what JP_DIR vs EN_DIR have different
print(f"\n=== ENG dir contents (verify ENG copy is intact) ===")
en_files = set(os.listdir(EN_DIR))
jp_files = set(os.listdir(JP_DIR))
missing = jp_files - en_files
extra = en_files - jp_files
if missing: print(f"  MISSING from ENG: {missing}")
if extra:   print(f"  EXTRA in ENG: {extra}")
if not missing and not extra:
    print(f"  ENG dir mirrors JP dir ✓")

# Compare sall.snl byte-by-byte at start
with open(os.path.join(JP_DIR,'sall.snl'),'rb') as f: jp_snl = f.read(32)
with open(os.path.join(EN_DIR,'sall.snl'),'rb') as f: en_snl = f.read(32)
print(f"  JP sall.snl first 32 bytes: {jp_snl.hex()}")
print(f"  EN sall.snl first 32 bytes: {en_snl.hex()}")
