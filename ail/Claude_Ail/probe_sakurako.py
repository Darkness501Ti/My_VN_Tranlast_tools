"""Inspect Sakurako game files for untranslated JP text sources."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings, find_strings_region

base = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\SAKURAKODL"

# 1. List all files + sizes
print("=== Files in game dir ===")
for name in sorted(os.listdir(base)):
    p = os.path.join(base, name)
    if os.path.isfile(p):
        sz = os.path.getsize(p)
        print(f"  {name:25s} {sz:>14,d}")

# 2. Inspect sall.snl current state (is it translated?)
print("\n=== sall.snl status ===")
snl_path = os.path.join(base, 'sall.snl')
sz = os.path.getsize(snl_path)
print(f"  size: {sz:,d}")
# Sniff for English content
with open(snl_path, 'rb') as f:
    data = f.read()
ascii_chunks = data.count(b'the ') + data.count(b'and ') + data.count(b' is ')
print(f"  ASCII 'the/and/is' occurrences: {ascii_chunks}")
# Sniff for JP hiragana sequences
jp_chunks = data.count(b'\x82\xb5') + data.count(b'\x82\xa9') + data.count(b'\x82\xcc')
print(f"  SJIS hiragana の/し/か runs: {jp_chunks}")

# 3. Check Ball.dat — may contain text/script
print("\n=== Ball.dat inspection ===")
ball = os.path.join(base, 'Ball.dat')
sz = os.path.getsize(ball)
print(f"  size: {sz:,d}")
with open(ball, 'rb') as f:
    head = f.read(64)
print(f"  head: {head[:32].hex()}")
# Try as archive
try:
    count = struct.unpack_from('<I', head, 0)[0]
    print(f"  if archive count: {count}")
    if 0 < count < 10000:
        c, sizes, blobs = read_archive(ball)
        # find first non-empty entry, try to decode
        for i, b in enumerate(blobs):
            if not b: continue
            payload, info = decode_entry(b)
            print(f"  entry {i}: {len(payload)} bytes, packed={info.get('packed')}")
            strs = extract_sjis_strings(payload, min_bytes=8)
            print(f"    SJIS strings >=4 chars: {len(strs)}")
            for off, ln, s in strs[:3]:
                print(f"      @0x{off:04x} {s!r}")
            if i >= 2:
                break
except Exception as e:
    print(f"  not an archive: {e}")

# 4. Check logo1.dat
print("\n=== logo1.dat inspection ===")
logo = os.path.join(base, 'logo1.dat')
print(f"  size: {os.path.getsize(logo):,d}")
with open(logo, 'rb') as f:
    head = f.read(32)
print(f"  head: {head.hex()}")
if head[:8] == b'\x89PNG\r\n\x1a\n':
    print("  -> raw PNG file")
elif head[:4] == b'BM':
    print("  -> BMP")

# 5. Check Thelp.dat - might have menu/UI text
print("\n=== Thelp.dat inspection ===")
thelp = os.path.join(base, 'Thelp.dat')
print(f"  size: {os.path.getsize(thelp):,d}")
try:
    c, sizes, blobs = read_archive(thelp)
    print(f"  archive count: {c}")
    n_packed = sum(1 for b in blobs if b and len(b)>=6 and struct.unpack_from('<H', b, 0)[0] == 1)
    print(f"  packed entries: {n_packed}")
    # decode first packed
    for i, b in enumerate(blobs):
        if not b: continue
        payload, info = decode_entry(b)
        if info.get('packed'):
            strs = extract_sjis_strings(payload, min_bytes=4)
            print(f"  entry {i}: {len(payload)} bytes, {len(strs)} SJIS strings")
            for off, ln, s in strs[:5]:
                print(f"    {s!r}")
            break
except Exception as e:
    print(f"  not parseable: {e}")

# 6. Check exe for JP
print("\n=== sakurakoDL.exe scan ===")
exe = os.path.join(base, 'sakurakoDL.exe')
with open(exe, 'rb') as f:
    data = f.read()
print(f"  size: {len(data):,d}")
strs = extract_sjis_strings(data, min_bytes=8)
real_jp = [(o, l, s) for o, l, s in strs if not all(c in '瑞瑞' for c in s)]
print(f"  total SJIS strings >= 4 chars: {len(strs)}, non-trivial: {len(real_jp)}")
for o, l, s in real_jp[:10]:
    print(f"    @0x{o:06x} {s!r}")

# 7. Sample sall.snl entries to confirm translation actually happened
print("\n=== sall.snl entry sample ===")
c, sizes, blobs = read_archive(snl_path)
print(f"  count: {c}, nonzero: {sum(1 for s in sizes if s)}")
# Pick entry 0 (menu)
payload, info = decode_entry(blobs[0])
print(f"  entry 0: {len(payload)} bytes")
# Find ASCII English runs
runs = []
i = 0
while i < len(payload):
    if 0x20 <= payload[i] <= 0x7E:
        j = i
        while j < len(payload) and 0x20 <= payload[j] <= 0x7E:
            j += 1
        if j - i >= 6:
            runs.append((i, payload[i:j].decode('ascii', errors='replace')))
        i = j
    else:
        i += 1
print(f"  ASCII English runs in entry 0:")
for off, s in runs[:8]:
    print(f"    @0x{off:04x} {s!r}")
