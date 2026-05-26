"""Compare original LZSS bytes vs my re-encoded bytes for entry 48.

Theory: my LZSS encoder produces a valid stream that my decoder accepts
but the engine's decoder may have additional constraints (e.g., end-of-
stream marker, terminator byte, specific bit padding).
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry, lzss_pack, lzss_unpack

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
count, sizes, blobs = read_archive(os.path.join(base, 'sall.snl'))

# Entry 48 inspect
blob = blobs[48]
print(f"Entry 48 in archive: {len(blob)} bytes (incl 6-byte prefix)")
print(f"  prefix     : {blob[:6].hex()}  =  u16={struct.unpack('<H', blob[:2])[0]}  u32={struct.unpack('<I', blob[2:6])[0]}")
print(f"  LZSS body  : {len(blob)-6} bytes")
print(f"  first 32   : {blob[6:38].hex()}")
print(f"  last 16    : {blob[-16:].hex()}")

# Decompress original
payload = lzss_unpack(blob[6:], struct.unpack('<I', blob[2:6])[0])
print(f"\nDecompressed payload: {len(payload)} bytes")

# Recompress
recompressed = lzss_pack(payload)
print(f"\nMy recompressed body: {len(recompressed)} bytes  (orig {len(blob)-6}, diff {len(recompressed)-(len(blob)-6):+d})")
print(f"  first 32   : {recompressed[:32].hex()}")
print(f"  last 16    : {recompressed[-16:].hex()}")

# Compare byte-for-byte where they overlap
common = min(len(blob)-6, len(recompressed))
diffs = 0
first_diff = None
for i in range(common):
    if blob[6+i] != recompressed[i]:
        diffs += 1
        if first_diff is None:
            first_diff = i
print(f"\nByte-for-byte diff (first {common} bytes): {diffs} bytes differ")
if first_diff is not None:
    print(f"  first diff at byte {first_diff} (in LZSS body):")
    print(f"    orig: {blob[6+first_diff:6+first_diff+16].hex()}")
    print(f"    mine: {recompressed[first_diff:first_diff+16].hex()}")

# Round-trip my output to verify it decodes
re_decoded = lzss_unpack(recompressed, len(payload))
print(f"\nRound-trip check: my_decoded == orig_payload? {re_decoded == payload}")

# Check: does original have a TRAILING byte after LZSS end?
# Try decompressing original with bigger output target to see if it stops
# at the right place.
print(f"\n=== Probe: does original LZSS stream have padding/terminator? ===")
# decompress to (output_size + 8) and see if we read additional input bytes
try:
    extra_out = lzss_unpack(blob[6:], len(payload) + 16)
    # how much of input did we consume?
    print(f"  decompressed past target: produced {len(extra_out)} bytes ({len(payload)+16} requested)")
    print(f"  extra bytes (after expected end): {extra_out[len(payload):].hex()}")
except Exception as e:
    print(f"  errored: {e}")

# Same for my output
try:
    my_extra = lzss_unpack(recompressed, len(payload) + 16)
    print(f"\n  my-output extra bytes: {my_extra[len(payload):].hex()}")
except Exception as e:
    print(f"  my output errored at extra read: {e}")

# Maybe the engine validates that the FINAL control byte has no leftover bits
# (i.e., padding bits in final ctl byte must be 0).
# Try: dump the LAST few control flow ops of the original vs mine.

# Show very last LZSS instructions
print(f"\n=== Last bytes of orig LZSS body ===")
print(f"  hex: {blob[-32:].hex()}")
print(f"=== Last bytes of my LZSS body ===")
print(f"  hex: {recompressed[-32:].hex()}")
