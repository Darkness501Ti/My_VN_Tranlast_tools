"""Check ALL clusters in sakurakoDL for ASCII voice-tag pattern.

If a cluster's first SJIS string is immediately preceded by an ASCII run
of >= 3 chars, that string is a SCENE TITLE used by the engine for voice
lookups. Don't translate it.
"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings, find_strings_region

SAK = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl"
count, sizes, blobs = read_archive(SAK)

def find_ascii_before(payload, off, max_lookback=8):
    """Find an ASCII run ending right before `off`. Returns (start, ascii_str) or None."""
    if off < 3: return None
    # walk back through ASCII printable chars
    i = off
    while i > 0 and i > off - max_lookback:
        c = payload[i - 1]
        if 0x20 <= c <= 0x7E and c not in (0x5B, 0x5D):
            i -= 1
        else:
            break
    if off - i >= 3:
        try:
            return (i, payload[i:off].decode('ascii'))
        except UnicodeDecodeError:
            return None
    return None

# Scan all entries — find ASCII-tagged strings (scene titles)
print(f"=== ASCII-tagged SJIS strings across sakurakoDL ===")
total_tagged = 0
total_clusters_with_tag = 0
sample = []
for idx, blob in enumerate(blobs):
    if not blob: continue
    payload, info = decode_entry(blob)
    if not info.get('packed'): continue
    strs = extract_sjis_strings(payload)
    region = find_strings_region(strs)
    # Group into clusters
    if not region: continue
    clusters = [[region[0]]]
    for s in region[1:]:
        gap = s[0] - (clusters[-1][-1][0] + clusters[-1][-1][1])
        if gap <= 16:
            clusters[-1].append(s)
        else:
            clusters.append([s])
    # For each cluster, check first string for ASCII prefix
    for c in clusters:
        first = c[0]
        ascii_pre = find_ascii_before(payload, first[0])
        if ascii_pre:
            total_tagged += 1
            total_clusters_with_tag += 1
            if len(sample) < 20:
                sample.append((idx, ascii_pre, first))

print(f"  entries with packed payload: {sum(1 for b in blobs if b and len(b)>=6 and __import__('struct').unpack_from('<H',b,0)[0]==1)}")
print(f"  cluster-first strings with ASCII tag: {total_clusters_with_tag}")
print(f"\n  Sample:")
for idx, (ap_off, ap_str), (s_off, s_ln, s_txt) in sample:
    print(f"    entry {idx:3d}: tag@0x{ap_off:04x} {ap_str!r:>16}  ->  scene@0x{s_off:04x} {s_txt!r}")

# Also check entry 51 specifically
print(f"\n=== Detail: entry 51 ===")
payload51, _ = decode_entry(blobs[51])
strs51 = extract_sjis_strings(payload51)
region51 = find_strings_region(strs51)
clusters51 = [[region51[0]]]
for s in region51[1:]:
    gap = s[0] - (clusters51[-1][-1][0] + clusters51[-1][-1][1])
    if gap <= 16:
        clusters51[-1].append(s)
    else:
        clusters51.append([s])
print(f"  total clusters: {len(clusters51)}")
for ci, c in enumerate(clusters51):
    first = c[0]
    pre = find_ascii_before(payload51, first[0])
    pre_repr = f"ASCII={pre[1]!r}" if pre else "(no ASCII tag)"
    print(f"  cluster {ci}: {len(c)} strings, starts @0x{first[0]:04x}, pre: {pre_repr}, first text: {first[2]!r}")
