"""Audit the new heuristic against both games — make sure it doesn't pull in
bytecode-noise that would crash the engine."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings, find_strings_region


def find_all_real_clusters(strs, min_cluster_size=3, max_intracluster_gap=16, max_median_gap=4):
    """Find ALL dense string clusters. Real clusters have median gap == 2 (the
    engine's `00 00` separator). Bytecode false-positive clusters have random
    gaps."""
    if not strs:
        return []
    clusters = []
    current = [strs[0]]
    for i in range(1, len(strs)):
        gap = strs[i][0] - (current[-1][0] + current[-1][1])
        if gap <= max_intracluster_gap:
            current.append(strs[i])
        else:
            clusters.append(current)
            current = [strs[i]]
    clusters.append(current)

    out = []
    for c in clusters:
        if len(c) < min_cluster_size:
            continue
        gaps = [c[i+1][0] - (c[i][0] + c[i][1]) for i in range(len(c) - 1)]
        if not gaps:
            continue
        median_gap = sorted(gaps)[len(gaps) // 2]
        if median_gap > max_median_gap:
            continue
        out.extend(c)
    return out


GAMES = [
    ("kouhouDL", r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL\sall.snl"),
    ("sakurakoDL", r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl"),
]

for game, snl in GAMES:
    print(f"\n========== {game} ==========")
    count, sizes, blobs = read_archive(snl)
    total_old = 0
    total_new = 0
    diffs = []
    for idx, blob in enumerate(blobs):
        if not blob: continue
        try:
            payload, info = decode_entry(blob)
        except:
            continue
        if not info.get('packed'): continue
        strs = extract_sjis_strings(payload)
        old_region = find_strings_region(strs)
        new_region = find_all_real_clusters(strs)
        total_old += len(old_region)
        total_new += len(new_region)
        if len(new_region) > len(old_region):
            diffs.append((idx, len(strs), len(old_region), len(new_region)))

    print(f"  total entries: {count}")
    print(f"  strings (old heuristic): {total_old}")
    print(f"  strings (new heuristic): {total_new}")
    print(f"  difference: +{total_new - total_old}")
    print(f"  entries with MORE strings under new heuristic:")
    for idx, gross, old, new in diffs[:20]:
        print(f"    entry {idx:3d}: gross={gross:3d} old={old:3d} new={new:3d}  (+{new-old})")
    if len(diffs) > 20:
        print(f"    ... and {len(diffs)-20} more")
