"""Check sakurakoDL voice files for filename/index references in the script."""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ail_lzss import read_archive, decode_entry

SAK_DIR = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\SAKURAKODL"
SAK_SRC = r"D:\game_install\501game\Baiin Reijou Suouin Sakurako no Zaiwai\sall.snl"

# 1. Look at vall01.dat structure
vall = os.path.join(SAK_DIR, 'vall01.dat')
sz = os.path.getsize(vall)
print(f"=== vall01.dat ({sz:,d} bytes) ===")
count, sizes, blobs = read_archive(vall)
print(f"  count: {count}, nonzero: {sum(1 for s in sizes if s)}")
# look at first entry's header
for i in range(min(5, len(blobs))):
    if not blobs[i]: continue
    head = blobs[i][:32]
    print(f"  entry {i}: size={len(blobs[i]):,d}, head={head.hex()}")

# 2. Decompressed sall.snl entry 51 - look for ASCII strings (voice file IDs)
print(f"\n=== sall.snl entry 51 - hunt for ASCII identifiers ===")
count, sizes, blobs = read_archive(SAK_SRC)
payload, _ = decode_entry(blobs[51])
print(f"  payload size: {len(payload)}")

# scan for printable ASCII runs
runs = []
i = 0
while i < len(payload):
    if 0x20 <= payload[i] <= 0x7E:
        j = i
        while j < len(payload) and 0x20 <= payload[j] <= 0x7E:
            j += 1
        if j - i >= 4:
            runs.append((i, payload[i:j]))
        i = j
    else:
        i += 1
print(f"  found {len(runs)} ASCII runs >=4 chars:")
for off, b in runs[:30]:
    print(f"    @0x{off:04x} [{len(b)}B] {b!r}")

# 3. Compare to kouhouDL - does it have similar ASCII?
KOU_SRC = r"D:\game_install\501Translate\waiting to Tranlaste\JP\kouhouDL\sall.snl"
print(f"\n=== kouhouDL sall.snl entry 50 - ASCII runs ===")
count_k, _, blobs_k = read_archive(KOU_SRC)
payload_k, _ = decode_entry(blobs_k[50])
runs_k = []
i = 0
while i < len(payload_k):
    if 0x20 <= payload_k[i] <= 0x7E:
        j = i
        while j < len(payload_k) and 0x20 <= payload_k[j] <= 0x7E:
            j += 1
        if j - i >= 4:
            runs_k.append((i, payload_k[i:j]))
        i = j
    else:
        i += 1
print(f"  found {len(runs_k)} ASCII runs >=4 chars:")
for off, b in runs_k[:30]:
    print(f"    @0x{off:04x} [{len(b)}B] {b!r}")
