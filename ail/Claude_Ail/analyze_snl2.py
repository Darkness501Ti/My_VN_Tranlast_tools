"""Hunt complete dialogue strings in sall.snl entries."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')

base = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL"
data = open(os.path.join(base, 'sall.snl'), 'rb').read()
count = struct.unpack_from('<I', data, 0)[0]
sizes = list(struct.unpack_from(f'<{count}I', data, 4))
hdr_end = 4 + count*4
blobs = []
off = hdr_end
for s in sizes:
    blobs.append(data[off:off+s] if s else b'')
    off += s

def is_sjis_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC

def is_sjis_trail(b):
    return 0x40 <= b <= 0xFC and b != 0x7F

def is_sjis_single(b):
    """SJIS half-width kana or ASCII."""
    return 0x20 <= b <= 0x7E or 0xA1 <= b <= 0xDF

def find_complete_sjis_runs(blob, min_chars=4):
    """Find runs of valid SJIS that end with 0x00 or another terminator."""
    results = []
    i = 0
    n = len(blob)
    while i < n:
        # try to start a SJIS run at i
        if i+1 < n and is_sjis_lead(blob[i]) and is_sjis_trail(blob[i+1]):
            start = i
            chars = 0
            j = i
            while j+1 < n and is_sjis_lead(blob[j]) and is_sjis_trail(blob[j+1]):
                j += 2
                chars += 1
            if chars >= min_chars:
                raw = blob[start:j]
                try:
                    s = raw.decode('shift_jis')
                    # context byte before/after
                    pre = blob[max(0,start-4):start].hex()
                    post = blob[j:j+4].hex()
                    results.append((start, len(raw), s, pre, post))
                except UnicodeDecodeError:
                    pass
            i = j
        else:
            i += 1
    return results

# Pick a chunky entry — entry 50 had 78 strings
for idx in [5, 50, 100]:
    blob = blobs[idx]
    if not blob:
        continue
    print(f"=== Entry {idx} ({len(blob)} bytes)")
    runs = find_complete_sjis_runs(blob, min_chars=4)
    print(f"  total runs with >=4 chars: {len(runs)}")
    for start, n, s, pre, post in runs[:25]:
        print(f"  @0x{start:04x} len={n:3d} pre={pre} post={post}  {s!r}")
    print(f"  ... (last 10)")
    for start, n, s, pre, post in runs[-10:]:
        print(f"  @0x{start:04x} len={n:3d} pre={pre} post={post}  {s!r}")
    print()

# Detect what bytes precede dialogue (length prefix pattern)
print("=== Byte-before-string analysis on entry 50 ===")
blob = blobs[50]
runs = find_complete_sjis_runs(blob, min_chars=8)
from collections import Counter
pre_counter = Counter()
for start, n, s, pre, post in runs:
    if start >= 2:
        pre_counter[blob[start-2:start].hex()] += 1
print(f"Most common 2-byte prefix before long SJIS runs:")
for prefix, c in pre_counter.most_common(15):
    print(f"  {prefix}: {c}x")

# Long run sample
print()
print("=== 10 longest dialogue strings across all entries ===")
all_runs = []
for idx, blob in enumerate(blobs):
    if not blob: continue
    for start, n, s, pre, post in find_complete_sjis_runs(blob, min_chars=10):
        all_runs.append((n, idx, start, s, pre, post))
all_runs.sort(reverse=True)
for n, idx, start, s, pre, post in all_runs[:10]:
    print(f"  entry{idx}@0x{start:04x} len={n} pre={pre} post={post}")
    print(f"    {s!r}")
