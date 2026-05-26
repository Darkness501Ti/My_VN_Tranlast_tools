"""Check whether kouhouDL entry 15's 132 'false positives' were actually real text."""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings

snl = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL\sall.snl"
count, sizes, blobs = read_archive(snl)
payload, info = decode_entry(blobs[15])
print(f"Entry 15: {len(payload)} bytes")

strs = extract_sjis_strings(payload, min_bytes=4)
print(f"Total SJIS detected: {len(strs)}")

# Show ALL strings with cluster info
prev_end = 0
cluster_id = 0
prev_off = -100
print(f"\nStrings with cluster boundaries:")
for i, (off, ln, s) in enumerate(strs):
    gap = off - prev_off if prev_off > 0 else 0
    if gap > 16:
        cluster_id += 1
        print(f"\n  --- Cluster {cluster_id} (gap {gap} bytes) ---")
    elif gap > 4:
        print(f"  ... gap {gap} ...")
    prev_off = off + ln
    print(f"  @0x{off:04x} [{ln:>3}B] {s!r}")
    if i > 60:
        print(f"  ... ({len(strs)-i} more)")
        break
