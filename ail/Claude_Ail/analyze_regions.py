"""Find the true 'strings region' boundary for each entry.

Theory: strings region is a contiguous cluster at the END of each entry's
decompressed payload. SJIS-looking bytes BEFORE that cluster are bytecode/
parameters that happen to have valid SJIS lead bytes. Replacing those
corrupts opcodes and crashes the engine (Scenario Code decode error).
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
count, sizes, blobs = read_archive(os.path.join(base, 'sall.snl'))

def find_string_region(payload, strs, max_gap=16):
    """Identify the contiguous strings region at the END of the entry.

    Walk strings list backwards; a string is 'in-region' if the gap to the
    next string is <= max_gap bytes. The region is the longest such suffix.
    Returns (region_start, region_strings) where region_strings is the
    sublist of strs inside the region.
    """
    if not strs:
        return None, []
    # last string is anchor
    region = [strs[-1]]
    for i in range(len(strs) - 2, -1, -1):
        cur = strs[i]
        nxt = strs[i + 1]
        gap = nxt[0] - (cur[0] + cur[1])
        if gap <= max_gap:
            region.insert(0, cur)
        else:
            break
    return region[0][0], region

# Analyze entry 48 specifically (the one that errored)
print(f"=== Entry 48 (the failing one) ===")
payload, info = decode_entry(blobs[48])
print(f"  size={len(payload)} bytes")
all_strs = extract_sjis_strings(payload, min_bytes=4)
print(f"  total SJIS runs detected (gross): {len(all_strs)}")

region_start, region_strs = find_string_region(payload, all_strs, max_gap=16)
print(f"  detected strings region: start=0x{region_start:04x} ({len(region_strs)} strings)")
print(f"  strings BEFORE region (NOT real, would corrupt): {len(all_strs) - len(region_strs)}")

# show NON-region strings (these are the corrupting false positives)
print(f"\n  FALSE POSITIVES (would corrupt bytecode):")
region_offsets = set(s[0] for s in region_strs)
for off, ln, s in all_strs:
    if off not in region_offsets:
        print(f"    @0x{off:04x} [{ln}B] {s!r}")
        if all_strs.index((off, ln, s)) > 5:
            break

# show region boundary
print(f"\n  REAL strings (first 5 in region):")
for off, ln, s in region_strs[:5]:
    print(f"    @0x{off:04x} [{ln}B] {s!r}")
print(f"  last in region:")
for off, ln, s in region_strs[-2:]:
    print(f"    @0x{off:04x} [{ln}B] {s!r}")

# Verify this heuristic across all entries
print(f"\n\n=== Heuristic verification across all entries ===")
total_real = 0
total_false_positives = 0
for idx, blob in enumerate(blobs):
    if not blob: continue
    payload, info = decode_entry(blob)
    if not info.get('packed'): continue
    strs = extract_sjis_strings(payload, min_bytes=4)
    if not strs: continue
    region_start, region_strs = find_string_region(payload, strs, max_gap=16)
    false_pos = len(strs) - len(region_strs)
    total_real += len(region_strs)
    total_false_positives += false_pos
    if false_pos > 0:
        print(f"  entry {idx:3d}: total={len(strs):3d}, real={len(region_strs):3d}, false={false_pos:3d}")

print(f"\n  TOTAL: real strings={total_real:,d}, false positives={total_false_positives:,d}")
print(f"  Original tool was patching false positives -> corruption")
