"""Analyze decompressed sall.snl entry to find string table and opcode structure."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
from ail_lzss import read_archive, decode_entry

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
count, sizes, blobs = read_archive(os.path.join(base, 'sall.snl'))

def find_sjis_strings(payload, min_chars=2):
    """Find all maximal SJIS-decodable runs. Returns list of (offset, byte_length, decoded)."""
    results = []
    i = 0
    n = len(payload)
    while i < n:
        b = payload[i]
        if (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC) and i + 1 < n:
            b2 = payload[i+1]
            if 0x40 <= b2 <= 0xFC and b2 != 0x7F:
                start = i
                while i + 1 < n:
                    b = payload[i]
                    if not (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC):
                        break
                    b2 = payload[i+1]
                    if not (0x40 <= b2 <= 0xFC and b2 != 0x7F):
                        break
                    i += 2
                if i - start >= min_chars * 2:
                    try:
                        s = payload[start:i].decode('shift_jis')
                        results.append((start, i - start, s))
                    except UnicodeDecodeError:
                        pass
                continue
        i += 1
    return results

# Analyze entry 50 (large narrative)
idx = 50
payload, info = decode_entry(blobs[idx])
print(f"=== Decompressed entry {idx}: {len(payload)} bytes")
print(f"  header hex[0..32]: {payload[:32].hex()}")
print()

# Parse possible header structure
# from analysis: bytes look like
# 00 00 00 00  c4 02 00 0b ab 23 00 00 00 00 00 00  ...
# Looking at entry 0: 00 00 00 00 18 00 b8 02 96 00 00 00 00 00 00 00
# Pattern: 4-byte zero, 4-byte field, more bytes...
u32s = struct.unpack_from('<8I', payload, 0)
print(f"  first 8 u32: {u32s}")
print()

# Find first SJIS string offset
strs = find_sjis_strings(payload, min_chars=3)
print(f"  total SJIS strings: {len(strs)}")
if strs:
    print(f"  FIRST string @0x{strs[0][0]:04x} ({strs[0][1]} bytes): {strs[0][2]!r}")
    print(f"  LAST string @0x{strs[-1][0]:04x} ({strs[-1][1]} bytes): {strs[-1][2]!r}")

# Look at what's RIGHT BEFORE first string and BETWEEN strings
print(f"\n  Bytes around first string @0x{strs[0][0]:04x}:")
s0 = strs[0][0]
pre = payload[max(0, s0-32):s0]
post = payload[s0+strs[0][1]:s0+strs[0][1]+8]
print(f"    pre  : {pre.hex()}")
print(f"    str  : {payload[s0:s0+strs[0][1]].hex()}")
print(f"    post : {post.hex()}")

# Find string table — look at u32/u16 values that point to string offsets
print(f"\n  Looking for offset-table pointing to string locations...")
string_offsets = set(s[0] for s in strs)
# scan for u16 LE values matching string offsets in first 0x1000 bytes
hits_u16 = 0
hits_u32 = 0
for off in range(0, min(len(payload), strs[0][0])):
    if off + 2 <= len(payload):
        v = struct.unpack_from('<H', payload, off)[0]
        if v in string_offsets:
            hits_u16 += 1
    if off + 4 <= len(payload):
        v = struct.unpack_from('<I', payload, off)[0]
        if v in string_offsets:
            hits_u32 += 1
print(f"    string offsets that appear as u16 in pre-string region: {hits_u16}")
print(f"    string offsets that appear as u32 in pre-string region: {hits_u32}")

# Show all distinct gaps between consecutive strings
gaps = []
prev_end = None
for off, bl, s in strs:
    if prev_end is not None:
        gap = off - prev_end
        gaps.append((gap, payload[prev_end:off]))
    prev_end = off + bl
from collections import Counter
gap_lens = Counter(g[0] for g in gaps)
print(f"\n  Most common inter-string gap lengths: {gap_lens.most_common(10)}")

# Show first 5 gap byte patterns
print(f"\n  First 8 inter-string gap byte sequences:")
for g, bs in gaps[:8]:
    print(f"    gap={g:>3d} bytes: {bs.hex()}")

# Show first 12 strings
print(f"\n  First 12 strings of entry {idx}:")
for off, bl, s in strs[:12]:
    print(f"    @0x{off:04x} [{bl:>3d}B] {s!r}")

# Look at entry 0 to compare structure
print(f"\n\n=== Decompressed entry 0: {len(decode_entry(blobs[0])[0])} bytes")
payload0, _ = decode_entry(blobs[0])
strs0 = find_sjis_strings(payload0, min_chars=2)
print(f"  header hex[0..64]: {payload0[:64].hex()}")
print(f"  string count: {len(strs0)}")
for off, bl, s in strs0[:8]:
    print(f"    @0x{off:04x} [{bl}B] {s!r}")

# Hex dump around string region in entry 0
if strs0:
    off0 = strs0[0][0]
    print(f"\n  Bytes from 0x{off0-16:04x} to 0x{off0+128:04x}:")
    region = payload0[max(0,off0-16):off0+128]
    for line in range(0, len(region), 16):
        chunk = region[line:line+16]
        addr = off0 - 16 + line
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        print(f"    {addr:04x}: {hexs}")
