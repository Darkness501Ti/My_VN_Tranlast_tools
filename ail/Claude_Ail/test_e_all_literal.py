"""Test E: encode each entry using ALL-LITERAL LZSS (no back-references).

This produces the LARGEST possible valid LZSS stream but the simplest -
no chance of back-ref bugs. If this works in-game we know back-ref
encoding is the bug. If this also fails we know something else is wrong
with our LZSS that we haven't found.
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, write_archive, decode_entry, lzss_unpack

def lzss_pack_all_literal(payload: bytes) -> bytes:
    """Encode bytes as LZSS with ALL literals (no back-refs)."""
    out = bytearray()
    src = 0
    n = len(payload)
    while src < n:
        # ctl byte: all bits = 0 (all literals)
        ctl = 0
        ops = bytearray()
        ops_count = 0
        while ops_count < 8 and src < n:
            ops.append(payload[src])
            src += 1
            ops_count += 1
        out.append(ctl)
        out.extend(ops)
    return bytes(out)

JP_DIR = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
EN_DIR = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL_ENG_ver"

count, sizes, blobs = read_archive(os.path.join(JP_DIR, 'sall.snl'))

# Recompress every entry as all-literal
new_blobs = []
new_sizes = []
for idx, blob in enumerate(blobs):
    if not blob:
        new_blobs.append(b'')
        new_sizes.append(0)
        continue
    payload, info = decode_entry(blob)
    if info.get('packed'):
        body = lzss_pack_all_literal(payload)
        # verify roundtrip
        check = lzss_unpack(body, len(payload))
        assert check == payload, f"roundtrip fail entry {idx}"
        entry = struct.pack('<HI', 1, len(payload)) + body
    else:
        entry = blob
    new_blobs.append(entry)
    new_sizes.append(len(entry))

out_path = os.path.join(EN_DIR, 'sall.snl')
write_archive(out_path, new_sizes, new_blobs)
print(f"  wrote {out_path}: all-literal LZSS recompression")
print(f"  output size: {os.path.getsize(out_path):,d} bytes (orig 524,561)")
print(f"  Copy to install dir and test")
