"""Test improved cluster-detection heuristic that finds ALL real string regions.

Theory: a "real" string cluster has:
  - >= 3 consecutive strings
  - inter-string gaps mostly == 2 bytes (the engine's `00 00` separator)
  - intra-cluster max gap <= 16

A bytecode-noise cluster has random gaps (sometimes happens to look like SJIS
in opcode parameters). Real string regions are tightly packed.
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry
from ail_translate import extract_sjis_strings

def find_all_real_clusters(strs, payload, min_cluster_size=3, max_intracluster_gap=16):
    """Return ALL real string clusters as a flat list of strings.

    A cluster qualifies as 'real' if:
      - Has >= min_cluster_size strings
      - Median inter-string gap <= 4 bytes (engine separator is 2 bytes; allow
        some 4-byte ruby brackets)
    """
    if not strs:
        return []
    # group adjacent strings
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
        # median gap
        gaps = [c[i+1][0] - (c[i][0] + c[i][1]) for i in range(len(c) - 1)]
        if not gaps: continue
        gaps_sorted = sorted(gaps)
        median_gap = gaps_sorted[len(gaps_sorted) // 2]
        if median_gap > 4:
            continue
        out.extend(c)
    return out


# Test cases
TESTS = [
    ("sakurakoDL entry 51 (should pick up BOTH clusters)",
     r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl",
     51,
     ['次の授業も', '一日の授業', 'クラスメイト']),
    ("kouhouDL entry 15 (was previously 132 false positives — should be 0 if pure bytecode noise, OR detect real cluster if any)",
     r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL\sall.snl",
     15,
     []),
    ("kouhouDL entry 48 (was the original crash entry)",
     r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL\sall.snl",
     48,
     ['オープニング']),
]

for label, snl_path, idx, needles in TESTS:
    print(f"\n=== {label} ===")
    count, sizes, blobs = read_archive(snl_path)
    payload, info = decode_entry(blobs[idx])
    strs = extract_sjis_strings(payload)
    real = find_all_real_clusters(strs, payload)
    print(f"  entry {idx}: {len(payload)}B, {len(strs)} gross, {len(real)} real (NEW heuristic)")

    # check needles
    for n in needles:
        encoded = n.encode('shift_jis')
        pos = payload.find(encoded)
        if pos < 0:
            print(f"  needle {n!r}: NOT FOUND in payload")
            continue
        # find the string containing this position
        for off, ln, s in real:
            if off <= pos < off + ln:
                print(f"  needle {n!r} @0x{pos:04x}: ✓ INCLUDED (string @0x{off:04x} = {s[:40]!r})")
                break
        else:
            print(f"  needle {n!r} @0x{pos:04x}: ✗ MISSED")

    # show cluster boundaries
    if real:
        cluster_starts = [real[0][0]]
        for i in range(1, len(real)):
            gap = real[i][0] - (real[i-1][0] + real[i-1][1])
            if gap > 16:
                cluster_starts.append(real[i][0])
        print(f"  clusters detected: {len(cluster_starts)}")
        for cs in cluster_starts:
            print(f"    starts @0x{cs:04x}")
