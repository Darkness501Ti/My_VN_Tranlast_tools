"""Compare what strings the NEW vs OLD heuristic includes in each entry.

If voice broke after new heuristic, the added clusters might contain
voice metadata that LOOKS like dialogue but is actually file references
or character indices.
"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings


def old_heuristic_suffix_only(strs, max_gap=16):
    """Old: only the dense suffix cluster."""
    if not strs:
        return []
    region = [strs[-1]]
    for i in range(len(strs) - 2, -1, -1):
        gap = strs[i + 1][0] - (strs[i][0] + strs[i][1])
        if gap <= max_gap:
            region.insert(0, strs[i])
        else:
            break
    return region


def new_heuristic_all_clusters(strs, max_gap=16):
    """New: all clusters with median gap <= 4."""
    if not strs:
        return []
    clusters = []
    current = [strs[0]]
    for i in range(1, len(strs)):
        gap = strs[i][0] - (current[-1][0] + current[-1][1])
        if gap <= max_gap:
            current.append(strs[i])
        else:
            clusters.append(current)
            current = [strs[i]]
    clusters.append(current)
    out = []
    for c in clusters:
        if len(c) < 3:
            continue
        gaps = [c[i + 1][0] - (c[i][0] + c[i][1]) for i in range(len(c) - 1)]
        median = sorted(gaps)[len(gaps) // 2]
        if median > 4:
            continue
        out.extend(c)
    return out


snl = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl"
count, sizes, blobs = read_archive(snl)

# entries with big differences (from earlier audit)
target_entries = [11, 47, 51, 52, 54, 55, 63, 74, 75]

for idx in target_entries:
    if not blobs[idx]: continue
    payload, info = decode_entry(blobs[idx])
    strs = extract_sjis_strings(payload)
    old = old_heuristic_suffix_only(strs)
    new = new_heuristic_all_clusters(strs)
    old_offs = set(s[0] for s in old)
    added = [s for s in new if s[0] not in old_offs]
    print(f"\n=== entry {idx} ({len(payload)}B) ===")
    print(f"  total gross: {len(strs)}, old: {len(old)}, new: {len(new)}, added by new: {len(added)}")
    if not added:
        continue
    # show first 10 added strings
    print(f"  Added strings (first 10):")
    for off, ln, s in added[:10]:
        # categorize: dialogue (long, has particles) vs metadata (short, no particles)
        has_particles = any(c in s for c in 'のはにをがでとも')
        marker = '[DIALOGUE]' if (ln > 12 and has_particles) else '[???maybe-metadata???]'
        print(f"    @0x{off:04x} [{ln:>3}B] {marker} {s!r}")
    # check if added cluster might be ALL short or ALL number-like
    short_strs = [s for s in added if s[1] < 12]
    print(f"  Short (<12B) strings: {len(short_strs)}/{len(added)}")
