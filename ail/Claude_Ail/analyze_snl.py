"""Analyze sall.snl internal entry structure - find Shift-JIS text."""
import os
import sys
import struct
import re
sys.stdout.reconfigure(encoding='utf-8')

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
snl_path = os.path.join(base, 'sall.snl')

with open(snl_path, 'rb') as f:
    data = f.read()

count = struct.unpack_from('<I', data, 0)[0]
sizes = list(struct.unpack_from(f'<{count}I', data, 4))
hdr_end = 4 + count*4

# extract each entry blob
blobs = []
off = hdr_end
for i, s in enumerate(sizes):
    if s == 0:
        blobs.append(b'')
    else:
        blobs.append(data[off:off+s])
        off += s

# Dump entry 0 in detail
print(f"=== sall.snl: count={count}, nonzero={sum(1 for s in sizes if s>0)}")
print(f"  hdr_end={hdr_end}, first10 sizes={sizes[:10]}")
print()

def find_sjis_strings(blob, min_len=4):
    """Find printable Shift-JIS strings."""
    results = []
    i = 0
    n = len(blob)
    cur_start = None
    cur_bytes = bytearray()
    while i < n:
        b = blob[i]
        # SJIS lead byte: 0x81-0x9F or 0xE0-0xFC
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            if i+1 < n:
                b2 = blob[i+1]
                if 0x40 <= b2 <= 0xFC and b2 != 0x7F:
                    if cur_start is None:
                        cur_start = i
                    cur_bytes.append(b)
                    cur_bytes.append(b2)
                    i += 2
                    continue
        # ASCII printable (in JP text could be embedded but rare for dialogue)
        if cur_start is not None and len(cur_bytes) >= min_len*2:
            try:
                s = cur_bytes.decode('shift_jis')
                results.append((cur_start, bytes(cur_bytes), s))
            except UnicodeDecodeError:
                pass
        cur_start = None
        cur_bytes = bytearray()
        i += 1
    # final
    if cur_start is not None and len(cur_bytes) >= min_len*2:
        try:
            s = cur_bytes.decode('shift_jis')
            results.append((cur_start, bytes(cur_bytes), s))
        except UnicodeDecodeError:
            pass
    return results

# Sample entries
for idx in [0, 1, 2, 5, 10, 50]:
    blob = blobs[idx]
    if not blob:
        continue
    print(f"--- Entry {idx} ({len(blob)} bytes)")
    print(f"  first 64 bytes hex: {blob[:64].hex()}")
    print(f"  last  32 bytes hex: {blob[-32:].hex()}")
    strs = find_sjis_strings(blob, min_len=3)
    print(f"  SJIS strings found: {len(strs)}")
    for off2, raw, s in strs[:8]:
        print(f"    @0x{off2:04x} [{len(raw)} bytes] {s!r}")
    print()
