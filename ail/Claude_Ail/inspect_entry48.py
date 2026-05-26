"""Inspect entry 48 string region structure - find if there's a length prefix."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
count, sizes, blobs = read_archive(os.path.join(base, 'sall.snl'))

payload, info = decode_entry(blobs[48])
print(f"Entry 48: {len(payload)} bytes")
strs = extract_sjis_strings(payload, min_bytes=4)
print(f"Strings found: {len(strs)}")
print(f"First string @ 0x{strs[0][0]:04x}: {strs[0][2]!r}")

# Dump bytes around first string and between first few strings
print(f"\nBytes around string boundaries (4 bytes before each + string + 4 after):")
for i in range(min(8, len(strs))):
    off, ln, s = strs[i]
    pre = payload[max(0,off-4):off]
    body = payload[off:off+ln]
    post = payload[off+ln:off+ln+4]
    print(f"  #{i} @0x{off:04x}: pre={pre.hex()}  body[{ln}B]={body.hex()[:24]}...  post={post.hex()}  '{s[:20]}'")

# Compare: what's at offset right before the region start?
print(f"\n80 bytes right before first string (0x{strs[0][0]-80:04x} .. 0x{strs[0][0]:04x}):")
for off in range(max(0, strs[0][0]-80), strs[0][0], 16):
    chunk = payload[off:off+16]
    print(f"  {off:04x}: {chunk.hex()}")

# Check if there's a count/table at start of region
print(f"\n16 bytes at very start of payload:")
print(f"  {payload[:16].hex()}")
print(f"  u16s: {struct.unpack('<8H', payload[:16])}")
print(f"  u32s: {struct.unpack('<4I', payload[:16])}")
