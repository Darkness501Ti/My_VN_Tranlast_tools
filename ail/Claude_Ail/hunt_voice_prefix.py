"""Scan all sakurakoDL entries for ASCII voice prefixes like 'a04_'."""
import os, sys, struct, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry

SAK_SRC = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl"
count, sizes, blobs = read_archive(SAK_SRC)

print(f"=== sakurakoDL: scan all entries for ASCII identifiers ===")
total_runs = 0
runs_by_entry = {}
all_run_patterns = []
for idx, blob in enumerate(blobs):
    if not blob: continue
    payload, info = decode_entry(blob)
    runs = []
    i = 0
    while i < len(payload):
        if 0x20 <= payload[i] <= 0x7E and payload[i] not in (0x5b, 0x5d):
            j = i
            while j < len(payload) and 0x20 <= payload[j] <= 0x7E and payload[j] not in (0x5b, 0x5d):
                j += 1
            if j - i >= 3:
                runs.append((i, payload[i:j].decode('ascii')))
            i = j
        else:
            i += 1
    if runs:
        runs_by_entry[idx] = runs
        total_runs += len(runs)
        all_run_patterns.extend(r[1] for r in runs)

print(f"  entries with ASCII runs: {len(runs_by_entry)}")
print(f"  total ASCII runs: {total_runs}")
print(f"\n  patterns (first 30 unique):")
from collections import Counter
pat_counter = Counter(all_run_patterns)
for p, c in pat_counter.most_common(30):
    print(f"    {c:>4}x  {p!r}")

# Show entries that have these prefixes + which strings come after
print(f"\n  Sample entry 51 ASCII run context:")
payload51, _ = decode_entry(blobs[51])
runs51 = runs_by_entry.get(51, [])
for off, s in runs51:
    # Show 16 bytes before and 24 bytes after
    pre = payload51[max(0, off-16):off]
    after = payload51[off+len(s):off+len(s)+24]
    print(f"    @0x{off:04x} pre={pre.hex()}  TAG={s!r}  after={after.hex()}")

# Check kouhouDL too
print(f"\n=== kouhouDL: check for similar identifiers ===")
KOU_SRC = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL\sall.snl"
count_k, _, blobs_k = read_archive(KOU_SRC)
kou_runs = 0
kou_patterns = []
for idx, blob in enumerate(blobs_k):
    if not blob: continue
    payload, _ = decode_entry(blob)
    i = 0
    while i < len(payload):
        if 0x20 <= payload[i] <= 0x7E and payload[i] not in (0x5b, 0x5d):
            j = i
            while j < len(payload) and 0x20 <= payload[j] <= 0x7E and payload[j] not in (0x5b, 0x5d):
                j += 1
            if j - i >= 3:
                kou_runs += 1
                kou_patterns.append(payload[i:j].decode('ascii'))
            i = j
        else:
            i += 1
print(f"  total ASCII runs: {kou_runs}")
print(f"  sample: {kou_patterns[:5]}")
